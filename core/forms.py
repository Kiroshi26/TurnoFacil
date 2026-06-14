from django import forms
import re


# ── VALIDADORES REUTILIZABLES ──

def validar_solo_letras(value):
    if re.search('[0-9]', value):
        raise forms.ValidationError('Este campo no puede contener numeros.')
    letras_validas = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ')
    letras_validas.update('aeiouAEIOUñÑüÜ -')
    for ch in value:
        if ch not in letras_validas:
            raise forms.ValidationError('Este campo solo puede contener letras.')


def validar_solo_numeros(value):
    if not re.match(r'^[0-9]+$', value):
        raise forms.ValidationError('Este campo solo puede contener números.')
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from datetime import timedelta
from .models import Usuario, Turno


# ── AUTH ──

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
    first_name       = forms.CharField(label='Nombre', max_length=100,
                         validators=[validar_solo_letras])
    last_name        = forms.CharField(label='Apellido', max_length=100,
                         validators=[validar_solo_letras])
    email            = forms.EmailField(label='Correo electrónico')
    tipo_documento   = forms.ChoiceField(
        label='Tipo de documento',
        choices=[('', 'Seleccionar…')] + [
            ('CC', 'Cédula de Ciudadanía'),
            ('TI', 'Tarjeta de Identidad'),
            ('CE', 'Cédula de Extranjería'),
            ('Pasaporte', 'Pasaporte'),
        ]
    )
    numero_documento = forms.CharField(label='Número de documento', max_length=30,
                         validators=[validar_solo_numeros])

    class Meta:
        model  = Usuario
        fields = ['first_name', 'last_name', 'username', 'email',
                  'tipo_documento', 'numero_documento', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email            = self.cleaned_data['email']
        user.tipo_documento   = self.cleaned_data['tipo_documento']
        user.numero_documento = self.cleaned_data['numero_documento']
        user.rol              = 'cliente'
        if commit:
            user.save()
        return user


# ── USUARIO ADMIN ──

class UsuarioAdminForm(forms.ModelForm):
    password   = forms.CharField(
        label='Contraseña', required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Dejar vacío para no cambiar'})
    )
    first_name = forms.CharField(label='Nombre',   max_length=100, validators=[validar_solo_letras])
    last_name  = forms.CharField(label='Apellido', max_length=100, required=False, validators=[validar_solo_letras])

    class Meta:
        model  = Usuario
        fields = ['first_name', 'last_name', 'username', 'email', 'rol', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd  = self.cleaned_data.get('password')
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user


# ── TURNO ──

def _horas_disponibles():
    horas = []
    hora = 8 * 60
    while hora <= 19 * 60:
        h = hora // 60
        m = hora % 60
        val = f'{h:02d}:{m:02d}'
        horas.append((val, val))
        hora += 30
    return horas


class TurnoForm(forms.ModelForm):
    hora = forms.ChoiceField(choices=_horas_disponibles, label='Hora')

    class Meta:
        model  = Turno
        fields = ['tipo_documento', 'numero_documento', 'motivo', 'fecha', 'hora', 'empleado']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        hoy    = timezone.localtime(timezone.now()).date()
        maxdia = hoy + timedelta(days=7)
        self.fields['fecha'].widget.attrs.update({
            'min': hoy.strftime('%Y-%m-%d'),
            'max': maxdia.strftime('%Y-%m-%d'),
        })
        self.fields['empleado'].queryset    = Usuario.objects.filter(rol='empleado')
        self.fields['empleado'].required    = False
        self.fields['empleado'].label       = 'Empleado asignado'
        self.fields['empleado'].empty_label = 'Sin asignar'

        # Si el usuario es cliente, pre-llenar y ocultar campos de documento
        if self.usuario and self.usuario.rol == 'cliente':
            # Usar initial no funciona con HiddenInput — hay que setear en data o en el campo directamente
            tipo = self.usuario.tipo_documento or ''
            num  = self.usuario.numero_documento or ''

            self.fields['tipo_documento'].widget    = forms.HiddenInput()
            self.fields['numero_documento'].widget  = forms.HiddenInput()
            self.fields['tipo_documento'].required  = False
            self.fields['numero_documento'].required= False

            # Si no viene data del POST, inyectar los valores del usuario
            if not self.data:
                self.initial['tipo_documento']   = tipo
                self.initial['numero_documento'] = num

    def clean_numero_documento(self):
        valor = self.cleaned_data.get('numero_documento', '')
        # Solo validar si el usuario es admin/empleado (cliente lo hereda del perfil)
        if self.usuario and self.usuario.rol != 'cliente' and valor:
            validar_solo_numeros(valor)
        return valor

    def clean(self):
        cleaned = super().clean()
        fecha   = cleaned.get('fecha')
        hora    = cleaned.get('hora')

        if fecha and hora:
            ahora = timezone.localtime(timezone.now())
            hoy   = ahora.date()

            if fecha < hoy:
                raise forms.ValidationError('La fecha no puede ser en el pasado.')

            if fecha == hoy:
                h, m     = map(int, hora.split(':'))
                min_slot = ahora.hour * 60 + ahora.minute + 30
                if h * 60 + m < min_slot:
                    raise forms.ValidationError(
                        f'La hora mínima disponible hoy es '
                        f'{min_slot // 60:02d}:{min_slot % 60:02d}.'
                    )
        return cleaned


class TurnoClienteForm(forms.ModelForm):
    """Solo hora y empleado — para clientes editando su turno."""
    hora = forms.ChoiceField(choices=_horas_disponibles, label='Hora')

    class Meta:
        model  = Turno
        fields = ['hora', 'empleado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['empleado'].queryset    = Usuario.objects.filter(rol='empleado')
        self.fields['empleado'].required    = False
        self.fields['empleado'].label       = 'Empleado asignado'
        self.fields['empleado'].empty_label = 'Sin asignar'


class TurnoEmpleadoForm(forms.ModelForm):
    """Fecha, hora, empleado y estado — para empleados."""
    hora = forms.ChoiceField(choices=_horas_disponibles, label='Hora')

    class Meta:
        model  = Turno
        fields = ['fecha', 'hora', 'empleado', 'estado']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['empleado'].queryset    = Usuario.objects.filter(rol='empleado')
        self.fields['empleado'].required    = False
        self.fields['empleado'].label       = 'Empleado asignado'
        self.fields['empleado'].empty_label = 'Sin asignar'


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