from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q
from django.core.mail import send_mail
from datetime import timedelta, date
import io


from .models import Usuario, Turno
from .forms import (
    LoginForm, RegistroForm, UsuarioAdminForm,
    TurnoForm, TurnoClienteForm, TurnoEmpleadoForm, PerfilForm
)
from .decorators import solo_admin, solo_cliente, solo_empleado, login_requerido
import logging
import json

logger = logging.getLogger('core')


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
    if user.rol == 'admin':
        return redirect('dashboard')
    if user.rol == 'empleado':
        return redirect('empleado_panel')
    return redirect('cliente_panel')


# ══════════════════════════════════════════
# DASHBOARD ADMIN
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def dashboard(request):
    hoy = timezone.localtime(timezone.now()).date()

    total_usuarios = Usuario.objects.count()
    total_turnos   = Turno.objects.count()
    turnos_hoy     = Turno.objects.filter(fecha=hoy).count()
    total_empleados= Usuario.objects.filter(rol='empleado').count()
    pendientes     = Turno.objects.filter(estado='Pendiente').count()
    atendidos      = Turno.objects.filter(estado='Atendido').count()
    cancelados     = Turno.objects.filter(estado='Cancelado').count()

    # Últimos 7 días para gráfica
    turnos_semana = []
    meses_es = {1:'Ene',2:'Feb',3:'Mar',4:'Abr',5:'May',6:'Jun',
                7:'Jul',8:'Ago',9:'Sep',10:'Oct',11:'Nov',12:'Dic'}
    dias_es  = {0:'Lun',1:'Mar',2:'Mié',3:'Jue',4:'Vie',5:'Sáb',6:'Dom'}
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        etiqueta = f"{dias_es[dia.weekday()]} {dia.day}"
        turnos_semana.append({
            'dia':      etiqueta,
            'total':    Turno.objects.filter(fecha=dia).count(),
            'pendiente':Turno.objects.filter(fecha=dia, estado='Pendiente').count(),
            'atendido': Turno.objects.filter(fecha=dia, estado='Atendido').count(),
        })

    ultimos_turnos = Turno.objects.select_related('cliente', 'empleado').order_by('-creado_en')[:5]

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
# TURNOS (ADMIN)
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def turnos_lista(request):
    turnos = Turno.objects.select_related('cliente', 'empleado').all()

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
        # Para clientes, inyectar documento del perfil en el POST
        data = request.POST.copy()
        if user.rol == 'cliente':
            data['tipo_documento']   = user.tipo_documento or ''
            data['numero_documento'] = user.numero_documento or ''
        form = TurnoForm(data, usuario=user)
    else:
        form = TurnoForm(usuario=user)

    if request.method == 'POST' and form.is_valid():
        try:
            turno = form.save(commit=False)
            turno.cliente = user
            turno.save()
            messages.success(request, 'Turno creado correctamente.')
            return _redirect_por_rol(user)
        except Exception as e:
            logger.error('Error al crear el turno: %s', str(e), exc_info=True)
            messages.error(request, f'Error al crear el turno: {str(e)}')

    return render(request, 'turnos/form.html', {'form': form, 'accion': 'Crear'})


@login_requerido
def turno_editar(request, pk):
    turno = get_object_or_404(Turno, pk=pk)
    user  = request.user

    # Permisos
    if user.rol == 'cliente' and turno.cliente != user:
        messages.error(request, 'No tienes permiso para editar este turno.')
        return redirect('cliente_panel')
    if user.rol == 'empleado' and turno.empleado != user:
        messages.error(request, 'No tienes permiso para editar este turno.')
        return redirect('empleado_panel')

    # Formulario según rol
    if user.rol == 'cliente':
        FormClass = TurnoClienteForm
    elif user.rol == 'empleado':
        FormClass = TurnoEmpleadoForm
    else:
        FormClass = TurnoForm

    form = FormClass(request.POST or None, instance=turno)
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
    turno = get_object_or_404(Turno, pk=pk)
    user  = request.user

    if user.rol == 'cliente' and turno.cliente != user:
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


@login_requerido
@solo_admin
def turnos_pdf(request):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    # Aplicar los mismos filtros que la lista
    q      = request.GET.get('q', '')
    estado = request.GET.get('estado', '')

    turnos = Turno.objects.select_related('cliente', 'empleado').all()
    if q:
        turnos = turnos.filter(
            Q(numero_turno__icontains=q) |
            Q(cliente__first_name__icontains=q) |
            Q(numero_documento__icontains=q)
        )
    if estado:
        turnos = turnos.filter(estado=estado)

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()
    story  = []

    # Título con filtros aplicados
    filtros_txt = []
    if q:      filtros_txt.append(f'Búsqueda: {q}')
    if estado: filtros_txt.append(f'Estado: {estado}')
    filtros_str = ' | '.join(filtros_txt) if filtros_txt else 'Sin filtros'

    story.append(Paragraph('TurnoFácil — Reporte de Turnos', styles['Title']))
    story.append(Paragraph(f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M")}', styles['Normal']))
    story.append(Paragraph(f'Filtros aplicados: {filtros_str}', styles['Normal']))
    story.append(Paragraph(f'Total de registros: {turnos.count()}', styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    # Tabla
    datos = [['N° Turno', 'Tipo Doc.', 'N° Documento', 'Motivo', 'Fecha', 'Hora', 'Estado', 'Empleado']]
    for t in turnos:
        datos.append([
            t.numero_turno,
            t.tipo_documento,
            t.numero_documento,
            t.motivo[:30] + '...' if len(t.motivo) > 30 else t.motivo,
            t.fecha.strftime('%d/%m/%Y'),
            t.hora,
            t.estado,
            t.empleado.get_full_name() if t.empleado else '—',
        ])

    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1916')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f7f5')]),
        ('FONTSIZE',   (0, 1), (-1, -1), 9),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#e8e6e1')),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',    (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla)
    doc.build(story)

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="turnos.pdf"'})


# ══════════════════════════════════════════
# USUARIOS (ADMIN)
# ══════════════════════════════════════════

@login_requerido
@solo_admin
def usuarios_lista(request):
    q        = request.GET.get('q', '')
    usuarios = Usuario.objects.all()
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
    form = UsuarioAdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'Usuario creado correctamente.')
            return redirect('usuarios_lista')
        except Exception as e:
            logger.error('Error al crear el usuario: %s', str(e), exc_info=True)
            messages.error(request, f'Error al crear el usuario: {str(e)}')
    return render(request, 'usuarios/form.html', {'form': form, 'accion': 'Crear'})


@login_requerido
@solo_admin
def usuario_editar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    form    = UsuarioAdminForm(request.POST or None, instance=usuario)
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
    usuario = get_object_or_404(Usuario, pk=pk)
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
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm

    usuarios = Usuario.objects.all()
    buffer   = io.BytesIO()
    doc      = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles   = getSampleStyleSheet()
    story    = []

    story.append(Paragraph('TurnoFácil — Reporte de Usuarios', styles['Title']))
    story.append(Paragraph(f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M")}', styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    datos = [['Nombre', 'Correo', 'Rol', 'Fecha registro']]
    for u in usuarios:
        datos.append([
            u.get_full_name() or u.username,
            u.email,
            u.get_rol_display(),
            u.date_joined.strftime('%d/%m/%Y'),
        ])

    tabla = Table(datos, repeatRows=1, colWidths=[5*cm, 7*cm, 3*cm, 3.5*cm])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1916')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f7f5')]),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#e8e6e1')),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING',    (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla)
    doc.build(story)

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="usuarios.pdf"'})


# ══════════════════════════════════════════
# PANEL CLIENTE
# ══════════════════════════════════════════

@login_requerido
@solo_cliente
def cliente_panel(request):
    user  = request.user
    turnos = Turno.objects.filter(cliente=user).order_by('-creado_en')

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
# LLAMAR TURNO (EMPLEADO)
# ══════════════════════════════════════════

@login_requerido
@solo_empleado
def llamar_turno(request, pk):
    turno = get_object_or_404(Turno, pk=pk, empleado=request.user)
    if request.method == 'POST':
        try:
            turno.llamado    = True
            turno.llamado_en = timezone.now()
            turno.save()

            # Enviar notificación por correo electrónico al cliente
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
                        None,  # Usa DEFAULT_FROM_EMAIL
                        [turno.cliente.email],
                        fail_silently=False,
                    )
                except Exception as mail_error:
                    logger.error('Error al enviar correo de notificación de turno: %s', str(mail_error), exc_info=True)

            return JsonResponse({'ok': True, 'numero_turno': turno.numero_turno})
        except Exception as e:
            logger.error('Error al llamar turno: %s', str(e), exc_info=True)
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': False}, status=405)



@login_requerido
def verificar_llamado(request):
    """El cliente hace polling para saber si su turno fue llamado."""
    turno = Turno.objects.filter(
        cliente=request.user,
        estado='Pendiente',
        llamado=True,
        fecha=timezone.localtime(timezone.now()).date()
    ).order_by('-llamado_en').first()

    if turno:
        # Marcar como visto para no volver a notificar
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
    """El admin puede cambiar estado directamente desde el dashboard."""
    if request.method == 'POST':
        turno  = get_object_or_404(Turno, pk=pk)
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
# PANEL EMPLEADO
# ══════════════════════════════════════════

@login_requerido
@solo_empleado
def empleado_panel(request):
    user  = request.user
    turnos = Turno.objects.filter(empleado=user).select_related('cliente').order_by('fecha', 'hora')

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