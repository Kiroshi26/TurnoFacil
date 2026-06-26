from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from datetime import timedelta, datetime
import io
import logging
import json

from .models import Usuario, Turno, Company
from .forms import (
    LoginForm, RegistroForm, TurnoForm, PerfilForm, generar_horas_empresa
)
from .decorators import solo_admin, solo_cliente, solo_empleado, login_requerido

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
# MIXIN DE SEGURIDAD (Row Level Security Lógico)
# ══════════════════════════════════════════

class TenantSecurityMixin(LoginRequiredMixin):
    """
    Mixin para garantizar el aislamiento de datos en Class-Based Views.
    Superusuarios acceden a todo; administradores y empleados ven solo su empresa;
    usuarios sin empresa asignada son rechazados.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 1. Acceso completo para el Administrador Global
        if self.request.user.is_superuser:
            return queryset
            
        # 2. Los clientes ven el queryset base (luego se filtra por su usuario)
        if self.request.user.rol == 'cliente':
            return queryset
            
        # 3. Denegar acceso si no tiene empresa asignada
        if not self.request.user.company:
            raise PermissionDenied(
                "Acceso Denegado: No tienes una empresa (Tenant) asignada a tu perfil."
            )
            
        # 4. Filtrar por la empresa del usuario
        return queryset.filter(company=self.request.user.company)


# Ejemplos de uso del TenantSecurityMixin para vistas basadas en clases
class TurnoListView(TenantSecurityMixin, ListView):
    """
    Ejemplo de vista CBV para listar turnos con RLS.
    """
    model = Turno
    template_name = 'turnos/lista_cbv.html'
    context_object_name = 'turnos'


# ══════════════════════════════════════════
# CLASES AUXILIARES DE REPORTE
# ══════════════════════════════════════════

from reportlab.pdfgen import canvas
from reportlab.lib import colors

class NumberedCanvas(canvas.Canvas):
    """
    Canvas personalizado para ReportLab que permite calcular y renderizar
    dinámicamente el número total de páginas en el pie de página de los reportes.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#6b7280'))
        
        self.setStrokeColor(colors.HexColor('#e2e8f0'))
        self.setLineWidth(0.5)
        
        width, height = self._pagesize
        margin = 1.5 * 28.34645
        
        self.line(margin, 1.2 * 28.34645, width - margin, 1.2 * 28.34645)
        
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(width - margin, 0.8 * 28.34645, page_text)
        self.drawString(margin, 0.8 * 28.34645, "TurnoFácil — Reporte oficial de sistema")
        self.restoreState()


# ══════════════════════════════════════════
# FUNCIÓN AUXILIAR DE SEGURIDAD PARA FBVs
# ══════════════════════════════════════════

def secure_tenant_filter(user, queryset_or_model):
    """
    Aplica las reglas de aislamiento para Function-Based Views.
    Retorna el QuerySet filtrado o levanta PermissionDenied.
    """
    if user.is_superuser:
        if isinstance(queryset_or_model, type):
            return queryset_or_model.objects.all()
        return queryset_or_model

    # Los clientes no están asociados a ninguna empresa; ven todo el set base
    # y su privacidad se maneja filtrando por su propio usuario (e.g. cliente=user).
    if user.rol == 'cliente':
        if isinstance(queryset_or_model, type):
            return queryset_or_model.objects.all()
        return queryset_or_model

    if not user.company:
        raise PermissionDenied("Acceso Denegado: No tienes una empresa asignada.")

    if isinstance(queryset_or_model, type):
        return queryset_or_model.objects.filter(company=user.company)
    return queryset_or_model.filter(company=user.company)


# ══════════════════════════════════════════
# API ENDPOINTS PARA AJAX (DISPONIBILIDAD Y EMPLEADOS POR TENANT)
# ══════════════════════════════════════════

def get_company_hours(request, company_id):
    """
    Endpoint AJAX que retorna la lista de horarios disponibles según el tenant.
    """
    try:
        comp = Company.objects.get(pk=company_id)
        choices = generar_horas_empresa(comp)
        return JsonResponse({'hours': [c[0] for c in choices]})
    except Company.DoesNotExist:
        return JsonResponse({'hours': []}, status=404)

def get_company_employees(request, company_id):
    """
    Endpoint AJAX que retorna los empleados asignados a un tenant específico.
    """
    employees = Usuario.objects.filter(company_id=company_id, rol='empleado')
    data = [{'id': emp.id, 'name': emp.get_full_name() or emp.username} for emp in employees]
    return JsonResponse({'employees': data})


# ══════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════

def login_view(request):
    if request.user.is_authenticated:
        return _redirect_por_rol(request.user)

    form = LoginForm(request.POST or None)
    error = None

    if request.method == 'POST' and form.is_valid():
        email    = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)
            return _redirect_por_rol(user)
        else:
            error = 'Correo o contraseña incorrectos.'

    return render(request, 'auth/login.html', {'form': form, 'error': error})


def registro_view(request):
    if request.user.is_authenticated:
        return _redirect_por_rol(request.user)

    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='core.backends.EmailBackend')
        messages.success(request, f'¡Bienvenido, {user.first_name}!')
        return redirect('cliente_panel')

    return render(request, 'auth/registro.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


def _redirect_por_rol(user):
    if user.is_superuser or user.rol == 'admin':
        return redirect('dashboard')
    if user.rol == 'empleado':
        return redirect('empleado_panel')
    return redirect('cliente_panel')


# ══════════════════════════════════════════
# DASHBOARD ADMIN (Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def dashboard(request):
    user = request.user
    hoy = timezone.localtime(timezone.now()).date()

    # Querysets base protegidos por empresa (excepto para superusuarios)
    usuarios_qs = secure_tenant_filter(user, Usuario)
    turnos_qs = secure_tenant_filter(user, Turno)

    total_usuarios = usuarios_qs.count()
    total_turnos   = turnos_qs.count()
    turnos_hoy     = turnos_qs.filter(fecha=hoy).count()
    total_empleados= usuarios_qs.filter(rol='empleado').count()
    pendientes     = turnos_qs.filter(estado='Pendiente').count()
    atendidos      = turnos_qs.filter(estado='Atendido').count()
    cancelados     = turnos_qs.filter(estado='Cancelado').count()

    turnos_semana = []
    meses_es = {1:'Ene',2:'Feb',3:'Mar',4:'Abr',5:'May',6:'Jun',
                7:'Jul',8:'Ago',9:'Sep',10:'Oct',11:'Nov',12:'Dic'}
    dias_es  = {0:'Lun',1:'Mar',2:'Mié',3:'Jue',4:'Vie',5:'Sáb',6:'Dom'}
    
    for i in range(7):
        dia = hoy + timedelta(days=i)
        etiqueta = f"{dias_es[dia.weekday()]} {dia.day}"
        turnos_semana.append({
            'dia':      etiqueta,
            'total':    turnos_qs.filter(fecha=dia).count(),
            'pendiente':turnos_qs.filter(fecha=dia, estado='Pendiente').count(),
            'atendido': turnos_qs.filter(fecha=dia, estado='Atendido').count(),
        })

    ultimos_turnos = turnos_qs.select_related('cliente', 'empleado').order_by('-creado_en')[:5]

    return render(request, 'dashboard.html', {
        'total_usuarios':  total_usuarios,
        'total_turnos':    total_turnos,
        'turnos_hoy':      turnos_hoy,
        'total_empleados': total_empleados,
        'pendientes':      pendientes,
        'atendidos':       atendidos,
        'cancelados':      cancelados,
        'turnos_semana':   turnos_semana,
        'ultimos_turnos':  ultimos_turnos,
        'chart_labels':    [t['dia']       for t in turnos_semana],
        'chart_pendientes':[t['pendiente'] for t in turnos_semana],
        'chart_atendidos': [t['atendido']  for t in turnos_semana],
    })


# ══════════════════════════════════════════
# TURNOS (ADMIN - Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def turnos_lista(request):
    user = request.user
    turnos = secure_tenant_filter(user, Turno).select_related('cliente', 'empleado')

    q      = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    
    if q:
        turnos = turnos.filter(
            Q(numero_turno__icontains=q) |
            Q(cliente__first_name__icontains=q) |
            Q(numero_documento__icontains=q)
        )
    if estado:
        turnos = turnos.filter(estado=estado)

    total      = turnos.count()
    pendientes = turnos.filter(estado='Pendiente').count()
    atendidos  = turnos.filter(estado='Atendido').count()

    return render(request, 'turnos/lista.html', {
        'turnos':     turnos,
        'total':      total,
        'pendientes': pendientes,
        'atendidos':  atendidos,
        'q':          q,
        'estado':     estado,
    })


@login_requerido
def turno_crear(request):
    user = request.user

    if request.method == 'POST':
        data = request.POST.copy()
        if user.rol == 'cliente' and not user.is_superuser:
            data['tipo_documento']   = user.tipo_documento or ''
            data['numero_documento'] = user.numero_documento or ''
        form = TurnoForm(data, user=user)
    else:
        form = TurnoForm(user=user)

    if request.method == 'POST' and form.is_valid():
        try:
            turno = form.save(commit=False)
            if user.rol == 'cliente' and not user.is_superuser:
                turno.cliente = user
                turno.company = form.cleaned_data['company']
            elif user.is_superuser:
                # El superusuario asocia el turno a la empresa elegida en el formulario
                turno.company = form.cleaned_data['company']
            else:
                # Para administradores y empleados de empresa, se asocia automáticamente a su empresa
                if not user.company:
                    raise PermissionDenied("El usuario no tiene una empresa asignada.")
                turno.company = user.company
            
            turno.save()
            messages.success(request, 'Turno creado correctamente.')
            return _redirect_por_rol(user)
        except Exception as e:
            logger.error('Error al crear el turno: %s', str(e), exc_info=True)
            messages.error(request, f'Error al crear el turno: {str(e)}')

    return render(request, 'turnos/form.html', {'form': form, 'accion': 'Crear'})


@login_requerido
def turno_editar(request, pk):
    user  = request.user
    
    # Obtener el turno y validar que pertenezca al inquilino correspondiente
    turnos_qs = secure_tenant_filter(user, Turno)
    turno = get_object_or_404(turnos_qs, pk=pk)

    # Validaciones adicionales basadas en el rol
    if user.rol == 'cliente' and not user.is_superuser and turno.cliente != user:
        messages.error(request, 'No tienes permiso para editar este turno.')
        return redirect('cliente_panel')

    form = TurnoForm(request.POST or None, instance=turno, user=user)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Turno actualizado correctamente.')
            return _redirect_por_rol(user)
        except Exception as e:
            logger.error('Error al actualizar el turno: %s', str(e), exc_info=True)
            messages.error(request, f'Error al actualizar el turno: {str(e)}')

    return render(request, 'turnos/form.html', {
        'form':   form,
        'turno':  turno,
        'accion': 'Editar',
    })


@login_requerido
def turno_eliminar(request, pk):
    user  = request.user
    turnos_qs = secure_tenant_filter(user, Turno)
    turno = get_object_or_404(turnos_qs, pk=pk)

    if user.rol == 'cliente' and not user.is_superuser and turno.cliente != user:
        messages.error(request, 'No tienes permiso.')
        return redirect('cliente_panel')

    if request.method == 'POST':
        try:
            turno.delete()
            messages.success(request, 'Turno eliminado correctamente.')
            return _redirect_por_rol(user)
        except Exception as e:
            logger.error('Error al eliminar el turno: %s', str(e), exc_info=True)
            messages.error(request, f'Error al eliminar el turno: {str(e)}')
            return _redirect_por_rol(user)

    return render(request, 'turnos/confirmar_eliminar.html', {'turno': turno})


# ══════════════════════════════════════════
# REPORTES PDF (Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def turnos_pdf(request):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm

    user = request.user
    q      = request.GET.get('q', '')
    estado = request.GET.get('estado', '')

    turnos = secure_tenant_filter(user, Turno).select_related('cliente', 'empleado')
    if q:
        turnos = turnos.filter(
            Q(numero_turno__icontains=q) |
            Q(cliente__first_name__icontains=q) |
            Q(numero_documento__icontains=q)
        )
    if estado:
        turnos = turnos.filter(estado=estado)

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=2.0*cm
    )
    story  = []

    style_title = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#111827'),
    )
    style_meta_right = ParagraphStyle(
        'DocMetaRight',
        fontName='Helvetica',
        fontSize=8.5,
        leading=13,
        textColor=colors.HexColor('#4b5563'),
        alignment=2
    )
    
    hdr_style = ParagraphStyle('HdrText', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)
    cell_style = ParagraphStyle('CellText', fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor('#1f2937'), leading=11)
    cell_code = ParagraphStyle('CellCode', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor('#4f46e5'), leading=11)
    
    filtros_txt = []
    if q:      filtros_txt.append(f'Búsqueda: {q}')
    if estado: filtros_txt.append(f'Estado: {estado}')
    filtros_str = ' | '.join(filtros_txt) if filtros_txt else 'Ninguno'

    empresa_txt = user.company.name if user.company else 'Global / Administrador'

    header_data = [
        [
            Paragraph(f'<font color="#4f46e5"><b>Turno</b></font><b>Fácil</b><font color="#94a3b8"><b> | </b></font><font color="#111827">Turnos de {empresa_txt}</font>', style_title),
            Paragraph(f'<b>Generado:</b> {timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")}<br/><b>Total:</b> {turnos.count()} registros<br/><b>Filtros:</b> {filtros_str}', style_meta_right)
        ]
    ]
    header_table = Table(header_data, colWidths=[16.7*cm, 10.0*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.1*cm))

    divider = Table([['']], colWidths=[26.7*cm], rowHeights=[2.5])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#4f46e5')),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 0.4*cm))

    def make_estado_badge(text, text_color, bg_color):
        badge_style = ParagraphStyle(
            'BadgeText', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor(text_color), alignment=1
        )
        p = Paragraph(text, badge_style)
        t = Table([[p]], colWidths=[2.2*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg_color)),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ]))
        return t

    headers = [
        Paragraph('N° Turno', hdr_style),
        Paragraph('Tipo Doc.', hdr_style),
        Paragraph('N° Documento', hdr_style),
        Paragraph('Motivo', hdr_style),
        Paragraph('Fecha', hdr_style),
        Paragraph('Hora', hdr_style),
        Paragraph('Estado', hdr_style),
        Paragraph('Empleado', hdr_style)
    ]
    datos = [headers]
    
    for t in turnos:
        if t.estado == 'Atendido':
            est_badge = make_estado_badge('Atendido', '#059669', '#d1fae5')
        elif t.estado == 'Cancelado':
            est_badge = make_estado_badge('Cancelado', '#dc2626', '#fee2e2')
        else:
            est_badge = make_estado_badge('Pendiente', '#d97706', '#fef3c7')

        datos.append([
            Paragraph(t.numero_turno, cell_code),
            Paragraph(t.tipo_documento, cell_style),
            Paragraph(t.numero_documento, cell_style),
            Paragraph(t.motivo, cell_style),
            Paragraph(t.fecha.strftime('%d/%m/%Y'), cell_style),
            Paragraph(t.hora, cell_style),
            est_badge,
            Paragraph(t.empleado.get_full_name() if t.empleado else '—', cell_style),
        ])

    col_widths = [2.5*cm, 2.2*cm, 3.0*cm, 7.0*cm, 2.5*cm, 2.0*cm, 3.0*cm, 4.5*cm]
    tabla = Table(datos, repeatRows=1, colWidths=col_widths)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="turnos.pdf"'})


# ══════════════════════════════════════════
# USUARIOS (ADMIN - Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def usuarios_lista(request):
    user = request.user
    q        = request.GET.get('q', '')
    usuarios = secure_tenant_filter(user, Usuario)
    
    if q:
        usuarios = usuarios.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(email__icontains=q)
        )
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios, 'q': q})


@login_requerido
@solo_admin
def usuario_crear(request):
    from .forms import UsuarioForm
    user = request.user
    
    form = UsuarioForm(request.POST or None, user=user)
    if request.method == 'POST' and form.is_valid():
        try:
            nuevo_usuario = form.save(commit=False)
            # Obligar que el usuario creado pertenezca a la misma empresa del admin
            if not user.is_superuser:
                nuevo_usuario.company = user.company
            nuevo_usuario.save()
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('usuarios_lista')
        except Exception as e:
            logger.error('Error al crear el usuario: %s', str(e), exc_info=True)
            messages.error(request, f'Error al crear el usuario: {str(e)}')
    return render(request, 'usuarios/form.html', {'form': form, 'accion': 'Crear'})


@login_requerido
@solo_admin
def usuario_editar(request, pk):
    from .forms import UsuarioForm
    user = request.user
    usuarios_qs = secure_tenant_filter(user, Usuario)
    usuario = get_object_or_404(usuarios_qs, pk=pk)
    
    form = UsuarioForm(request.POST or None, instance=usuario, user=user)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('usuarios_lista')
        except Exception as e:
            logger.error('Error al actualizar el usuario: %s', str(e), exc_info=True)
            messages.error(request, f'Error al actualizar el usuario: {str(e)}')
    return render(request, 'usuarios/form.html', {'form': form, 'accion': 'Editar', 'usuario': usuario})


@login_requerido
@solo_admin
def usuario_eliminar(request, pk):
    user = request.user
    usuarios_qs = secure_tenant_filter(user, Usuario)
    usuario = get_object_or_404(usuarios_qs, pk=pk)
    
    if request.user == usuario:
        messages.error(request, 'No puedes eliminarte a ti mismo.')
        return redirect('usuarios_lista')
        
    if request.method == 'POST':
        try:
            usuario.delete()
            messages.success(request, 'Usuario eliminado.')
            return redirect('usuarios_lista')
        except Exception as e:
            logger.error('Error al eliminar el usuario: %s', str(e), exc_info=True)
            messages.error(request, f'Error al eliminar el usuario: {str(e)}')
            return redirect('usuarios_lista')
            
    return render(request, 'usuarios/confirmar_eliminar.html', {'usuario': usuario})


@login_requerido
@solo_admin
def usuarios_pdf(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm

    user = request.user
    usuarios = secure_tenant_filter(user, Usuario).order_by('-date_joined')
    buffer   = io.BytesIO()
    
    doc      = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=2.0*cm
    )
    story    = []

    style_title = ParagraphStyle(
        'DocTitle', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor('#111827'),
    )
    style_meta_right = ParagraphStyle(
        'DocMetaRight', fontName='Helvetica', fontSize=8.5, leading=13, textColor=colors.HexColor('#4b5563'), alignment=2
    )
    
    hdr_style = ParagraphStyle('HdrText', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)
    cell_style = ParagraphStyle('CellText', fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor('#1f2937'), leading=11)
    
    empresa_txt = user.company.name if user.company else 'Global / Administrador'

    header_data = [
        [
            Paragraph(f'<font color="#4f46e5"><b>Turno</b></font><b>Fácil</b><font color="#94a3b8"><b> | </b></font><font color="#111827">Usuarios de {empresa_txt}</font>', style_title),
            Paragraph(f'<b>Generado:</b> {timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")}<br/><b>Total:</b> {usuarios.count()} usuarios', style_meta_right)
        ]
    ]
    header_table = Table(header_data, colWidths=[11.0*cm, 7.0*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.1*cm))

    divider = Table([['']], colWidths=[18.0*cm], rowHeights=[2.5])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#4f46e5')),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 0.4*cm))

    def make_rol_badge(text, text_color, bg_color):
        badge_style = ParagraphStyle(
            'BadgeText', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor(text_color), alignment=1
        )
        p = Paragraph(text, badge_style)
        t = Table([[p]], colWidths=[2.6*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg_color)),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ]))
        return t

    headers = [
        Paragraph('Nombre', hdr_style),
        Paragraph('Correo', hdr_style),
        Paragraph('Rol', hdr_style),
        Paragraph('Fecha registro', hdr_style)
    ]
    datos = [headers]
    
    for u in usuarios:
        if u.rol == 'admin':
            rol_badge = make_rol_badge('Administrador', '#7e22ce', '#f3e8ff')
        elif u.rol == 'empleado':
            rol_badge = make_rol_badge('Empleado', '#1d4ed8', '#dbeafe')
        else:
            rol_badge = make_rol_badge('Cliente', '#475569', '#f1f5f9')

        datos.append([
            Paragraph(u.get_full_name() or u.username, cell_style),
            Paragraph(u.email, cell_style),
            rol_badge,
            Paragraph(u.date_joined.strftime('%d/%m/%Y'), cell_style),
        ])

    col_widths = [5.0*cm, 6.5*cm, 3.0*cm, 3.5*cm]
    tabla = Table(datos, repeatRows=1, colWidths=col_widths)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
    ]))
    story.append(tabla)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="usuarios.pdf"'})


# ══════════════════════════════════════════
# PANEL CLIENTE (Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_cliente
def cliente_panel(request):
    user  = request.user
    
    # Si el cliente pertenece a una empresa, asegurar que sólo interactúe con sus turnos de esa empresa
    turnos = secure_tenant_filter(user, Turno).filter(cliente=user).order_by('-creado_en')

    pendientes    = turnos.filter(estado='Pendiente').count()
    atendidos     = turnos.filter(estado='Atendido').count()
    cancelados    = turnos.filter(estado='Cancelado').count()
    
    proximo_turno = turnos.filter(
        estado='Pendiente',
        fecha__gte=timezone.localtime(timezone.now()).date()
    ).order_by('fecha', 'hora').first()

    return render(request, 'cliente/panel.html', {
        'turnos':        turnos,
        'pendientes':    pendientes,
        'atendidos':     atendidos,
        'cancelados':    cancelados,
        'proximo_turno': proximo_turno,
    })


# ══════════════════════════════════════════
# LLAMAR TURNO (EMPLEADO - Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_empleado
def llamar_turno(request, pk):
    # Validar que el turno pertenezca a la empresa del empleado
    turnos_qs = secure_tenant_filter(request.user, Turno)
    # Solo permite llamar si está asignado a sí mismo o no tiene empleado asignado (None)
    turno = get_object_or_404(turnos_qs, Q(empleado=request.user) | Q(empleado__isnull=True), pk=pk)
    
    if request.method == 'POST':
        try:
            # Auto-asignarse al turno si no estaba asignado
            if not turno.empleado:
                turno.empleado = request.user
            turno.llamado    = True
            turno.llamado_en = timezone.now()
            turno.save()

            if turno.cliente.email:
                try:
                    subject = f"¡Tu turno {turno.numero_turno} ha sido llamado!"
                    message = (
                        f"Hola {turno.cliente.first_name or turno.cliente.username},\n\n"
                        f"Tu turno con código {turno.numero_turno} ha sido llamado por el empleado "
                        f"{request.user.get_full_name() or request.user.username}.\n"
                        f"Por favor acércate al módulo de atención.\n\n"
                        f"Detalles del turno:\n"
                        f"- Motivo: {turno.motivo}\n"
                        f"- Fecha: {turno.fecha.strftime('%d/%m/%Y')}\n"
                        f"- Hora: {turno.hora}\n\n"
                        f"¡Gracias por usar TurnoFácil!"
                    )
                    send_mail(
                        subject,
                        message,
                        None,
                        [turno.cliente.email],
                        fail_silently=False,
                    )
                except Exception as mail_error:
                    logger.error('Error al enviar correo de notificación: %s', str(mail_error), exc_info=True)

            return JsonResponse({'ok': True, 'numero_turno': turno.numero_turno})
        except Exception as e:
            logger.error('Error al llamar turno: %s', str(e), exc_info=True)
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': False}, status=405)


@login_requerido
def verificar_llamado(request):
    user = request.user
    # Asegurar que verificamos el llamado en la empresa correspondiente
    turnos_qs = secure_tenant_filter(user, Turno)
    turno = turnos_qs.filter(
        cliente=user,
        estado='Pendiente',
        llamado=True,
        fecha=timezone.localtime(timezone.now()).date()
    ).order_by('-llamado_en').first()

    if turno:
        turno.llamado = False
        turno.save()
        return JsonResponse({
            'llamado': True,
            'numero_turno': turno.numero_turno,
            'mensaje': f'¡Tu turno {turno.numero_turno} está siendo llamado!'
        })
    return JsonResponse({'llamado': False})


@login_requerido
@solo_admin
def cambiar_estado_turno(request, pk):
    if request.method == 'POST':
        turnos_qs = secure_tenant_filter(request.user, Turno)
        turno  = get_object_or_404(turnos_qs, pk=pk)
        estado = request.POST.get('estado')
        if estado in ['Pendiente', 'Atendido', 'Cancelado']:
            try:
                turno.estado = estado
                turno.save()
                return JsonResponse({'ok': True, 'estado': estado})
            except Exception as e:
                logger.error('Error al cambiar estado: %s', str(e), exc_info=True)
                return JsonResponse({'ok': False, 'error': str(e)}, status=500)
        return JsonResponse({'ok': False, 'error': 'Estado inválido'}, status=400)
    return JsonResponse({'ok': False}, status=405)


# ══════════════════════════════════════════
# PANEL EMPLEADO (Con Aislamiento Tenant)
# ══════════════════════════════════════════

@login_requerido
@solo_empleado
def empleado_panel(request):
    user  = request.user
    
    # Filtrar turnos por empresa
    turnos = secure_tenant_filter(user, Turno).select_related('cliente', 'empleado').order_by('fecha', 'hora')

    pendientes    = turnos.filter(estado='Pendiente').count()
    atendidos     = turnos.filter(estado='Atendido').count()
    cancelados    = turnos.filter(estado='Cancelado').count()
    hoy_local     = timezone.localtime(timezone.now()).date()
    turnos_hoy    = turnos.filter(fecha=hoy_local).count()
    
    proximo_turno = turnos.filter(
        estado='Pendiente',
        fecha__gte=hoy_local
    ).order_by('fecha', 'hora').first()

    return render(request, 'empleado/panel.html', {
        'turnos':        turnos,
        'pendientes':    pendientes,
        'atendidos':     atendidos,
        'cancelados':    cancelados,
        'turnos_hoy':    turnos_hoy,
        'proximo_turno': proximo_turno,
    })


@login_requerido
def editar_perfil(request):
    user = request.user
    form = PerfilForm(request.POST or None, instance=user)

    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return _redirect_por_rol(user)
        except Exception as e:
            logger.error('Error al actualizar perfil: %s', str(e), exc_info=True)
            messages.error(request, f'Error al actualizar el perfil: {str(e)}')

    return render(request, 'auth/perfil.html', {'form': form})