from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Turno, Usuario, Company
import re

def validar_solo_letras(value):
    if re.search('[0-9]', value):
        raise forms.ValidationError('Este campo no puede contener números.')
    letras_validas = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ')
    letras_validas.update('aeiouAEIOUñÑüÜáéíóúÁÉÍÓÚ -')
    for ch in value:
        if ch not in letras_validas:
            raise forms.ValidationError('Este campo solo puede contener letras.')

def validar_solo_numeros(value):
    if not re.match(r'^[0-9]+$', value):
        raise forms.ValidationError('Este campo solo puede contener números.')


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'placeholder': 'usuario@correo.com', 'autofocus': True})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'})
    )


class RegistroForm(UserCreationForm):
    first_name       = forms.CharField(label='Nombre', max_length=100, validators=[validar_solo_letras])
    last_name        = forms.CharField(label='Apellido', max_length=100, validators=[validar_solo_letras])
    email            = forms.EmailField(label='Correo electrónico')
    company          = forms.ModelChoiceField(queryset=Company.objects.all(), required=False, label="Empresa (Opcional)")
    tipo_documento   = forms.ChoiceField(
        label='Tipo de documento',
        choices=[('', 'Seleccionar…')] + [
            ('CC', 'Cédula de Ciudadanía'),
            ('TI', 'Tarjeta de Identidad'),
            ('CE', 'Cédula de Extranjería'),
            ('Pasaporte', 'Pasaporte'),
        ]
    )
    numero_documento = forms.CharField(label='Número de documento', max_length=30, validators=[validar_solo_numeros])

    class Meta:
        model  = Usuario
        fields = ['first_name', 'last_name', 'username', 'email', 'company', 'tipo_documento', 'numero_documento']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email            = self.cleaned_data['email']
        user.company          = self.cleaned_data['company']
        user.tipo_documento   = self.cleaned_data['tipo_documento']
        user.numero_documento = self.cleaned_data['numero_documento']
        user.rol              = 'cliente'
        if commit:
            user.save()
        return user


from django.utils import timezone
from datetime import timedelta

def generar_horas_empresa(company):
    """
    Genera la lista de horas disponibles en base a la configuración
    de negocio de la empresa.
    """
    config = company.business_config if company else {}
    slot_duration = config.get('slot_duration', 30)
    opening_str = config.get('opening_time', '08:00')
    closing_str = config.get('closing_time', '18:00')
    
    try:
        h_start, m_start = map(int, opening_str.split(':'))
        h_end, m_end = map(int, closing_str.split(':'))
    except (ValueError, AttributeError):
        h_start, m_start = 8, 0
        h_end, m_end = 18, 0
        
    start_minutes = h_start * 60 + m_start
    end_minutes = h_end * 60 + m_end
    
    choices = []
    curr = start_minutes
    while curr <= end_minutes:
        h = curr // 60
        m = curr % 60
        val = f"{h:02d}:{m:02d}"
        choices.append((val, val))
        curr += slot_duration
    return choices


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=True,
        label='Contraseña'
    )
    rol = forms.ChoiceField(
        choices=[
            ('admin', 'Administrador de Empresa'),
            ('empleado', 'Empleado'),
        ],
        label='Rol'
    )

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'username', 'email', 'rol', 'company']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Si estamos editando, la contraseña no es obligatoria
        if self.instance and self.instance.pk:
            self.fields['password'].required = False

        # Si el creador no es superusuario, no debe ver la opción de cambiar la empresa
        if self.user and not self.user.is_superuser:
            self.fields.pop('company', None)
        else:
            self.fields['company'].queryset = Company.objects.all()
            self.fields['company'].required = False
            self.fields['company'].label = "Empresa (Tenant)"

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class TurnoForm(forms.ModelForm):
    """
    Formulario para la gestión de turnos que limita las opciones de selección
    al tenant correspondiente y valida las relaciones inter-tenant.
    """
    hora = forms.ChoiceField(choices=[], label='Hora')

    class Meta:
        model = Turno
        fields = ['company', 'cliente', 'empleado', 'tipo_documento', 'numero_documento', 'motivo', 'fecha', 'hora', 'estado']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Se extrae el usuario actual que realiza la petición
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # 1. Configurar límites de fecha: Hoy hasta 7 días siguientes
            hoy = timezone.localtime(timezone.now()).date()
            maxdia = hoy + timedelta(days=7)
            self.fields['fecha'].widget.attrs.update({
                'min': hoy.strftime('%Y-%m-%d'),
                'max': maxdia.strftime('%Y-%m-%d'),
            })

            # 2. Configurar comportamiento según el Rol
            if self.user.rol == 'cliente' and not self.user.is_superuser:
                # Ocultar campos de documento y auto-llenar desde su perfil
                tipo = self.user.tipo_documento or ''
                num  = self.user.numero_documento or ''
                
                self.fields['tipo_documento'].widget    = forms.HiddenInput()
                self.fields['numero_documento'].widget  = forms.HiddenInput()
                self.fields['tipo_documento'].required  = False
                self.fields['numero_documento'].required= False
                
                if not self.data:
                    self.initial['tipo_documento']   = tipo
                    self.initial['numero_documento'] = num

                # Ocultar estado para que no lo puedan alterar
                self.fields['estado'].widget = forms.HiddenInput()
                self.fields['estado'].required = False
                self.fields['estado'].initial = 'Pendiente'
                
                # El cliente puede seleccionar cualquier empresa de la base de datos
                self.fields['company'].queryset = Company.objects.all()
                
                # Ocultar y auto-asignar el cliente a sí mismo
                self.fields['cliente'].widget = forms.HiddenInput()
                self.fields['cliente'].required = False
                self.fields['cliente'].initial = self.user
                
                # Cargar horas en base a la empresa seleccionada (si ya viene en POST o instancia)
                selected_company_id = self.data.get('company') or (self.instance.company.id if self.instance and self.instance.pk and self.instance.company else None)
                if selected_company_id:
                    try:
                        comp = Company.objects.get(id=selected_company_id)
                        self.fields['hora'].choices = generar_horas_empresa(comp)
                    except (Company.DoesNotExist, ValueError):
                        self.fields['hora'].choices = [('', 'Selecciona una empresa primero')]
                else:
                    self.fields['hora'].choices = [('', 'Selecciona una empresa primero')]

                # Eliminar el campo de empleado para que el cliente no pueda escogerlo
                self.fields.pop('empleado', None)
                    
            elif self.user.is_superuser:
                # El Superusuario ve todas las empresas y clientes
                self.fields['company'].queryset = Company.objects.all()
                self.fields['cliente'].queryset = Usuario.objects.filter(rol='cliente')
                
                selected_company_id = self.data.get('company') or (self.instance.company.id if self.instance and self.instance.pk and self.instance.company else None)
                if selected_company_id:
                    self.fields['empleado'].queryset = Usuario.objects.filter(company_id=selected_company_id, rol='empleado')
                    try:
                        comp = Company.objects.get(id=selected_company_id)
                        self.fields['hora'].choices = generar_horas_empresa(comp)
                    except (Company.DoesNotExist, ValueError):
                        self.fields['hora'].choices = [('', 'Selecciona una empresa primero')]
                else:
                    self.fields['empleado'].queryset = Usuario.objects.filter(rol='empleado')
                    self.fields['hora'].choices = [('', 'Selecciona una empresa primero')]
            else:
                # Administradores y empleados de empresa
                self.fields['company'].widget = forms.HiddenInput()
                self.fields['company'].required = False
                self.fields['company'].initial = self.user.company
                
                if self.instance and self.instance.pk:
                    # Al editar un turno, removemos el selector de cliente
                    self.fields.pop('cliente', None)
                else:
                    # Filtrar clientes por la empresa del admin/empleado al crear
                    self.fields['cliente'].queryset = Usuario.objects.filter(
                        company=self.user.company, rol='cliente'
                    )
                
                self.fields['empleado'].queryset = Usuario.objects.filter(
                    company=self.user.company, rol='empleado'
                )
                self.fields['hora'].choices = generar_horas_empresa(self.user.company)

    def clean(self):
        cleaned_data = super().clean()
        empleado = cleaned_data.get('empleado')
        
        # Obtener la empresa correspondiente
        company = cleaned_data.get('company')
        if not company and self.user and self.user.company:
            company = self.user.company
            
        # Validación de seguridad: el empleado debe pertenecer a la misma empresa del turno
        if empleado and company:
            if empleado.company != company:
                raise forms.ValidationError(
                    "Error de Seguridad: El empleado seleccionado pertenece a otra empresa."
                )
                
        return cleaned_data


class PerfilForm(forms.ModelForm):
    first_name       = forms.CharField(label='Nombre', max_length=100, validators=[validar_solo_letras])
    last_name        = forms.CharField(label='Apellido', max_length=100, validators=[validar_solo_letras])
    email            = forms.EmailField(label='Correo electrónico')
    tipo_documento   = forms.ChoiceField(
        label='Tipo de documento',
        choices=[('', 'Seleccionar…')] + [
            ('CC', 'Cédula de Ciudadanía'),
            ('TI', 'Tarjeta de Identidad'),
            ('CE', 'Cédula de Extranjería'),
            ('Pasaporte', 'Pasaporte'),
        ],
        required=False
    )
    numero_documento = forms.CharField(label='Número de documento', max_length=30, required=False)

    class Meta:
        model  = Usuario
        fields = ['first_name', 'last_name', 'email', 'tipo_documento', 'numero_documento']

    def clean_numero_documento(self):
        valor = self.cleaned_data.get('numero_documento', '')
        if valor:
            validar_solo_numeros(valor)
        return valor