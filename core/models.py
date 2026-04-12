from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import random
import string


class Usuario(AbstractUser):
    ROL_CHOICES = [
        ('admin',    'Administrador'),
        ('empleado', 'Empleado'),
        ('cliente',  'Cliente'),
    ]
    TIPO_DOC_CHOICES = [
        ('CC',        'Cédula de Ciudadanía'),
        ('TI',        'Tarjeta de Identidad'),
        ('CE',        'Cédula de Extranjería'),
        ('Pasaporte', 'Pasaporte'),
    ]

    email            = models.EmailField(unique=True)
    rol              = models.CharField(max_length=20, choices=ROL_CHOICES, default='cliente')
    tipo_documento   = models.CharField(max_length=20, choices=TIPO_DOC_CHOICES, blank=True, null=True, verbose_name='Tipo de documento')
    numero_documento = models.CharField(max_length=30, blank=True, null=True, verbose_name='Número de documento')

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.get_full_name() or self.username

    def is_admin(self):
        return self.rol == 'admin'

    def is_empleado(self):
        return self.rol == 'empleado'

    def is_cliente(self):
        return self.rol == 'cliente'


class Turno(models.Model):
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Atendido',  'Atendido'),
        ('Cancelado', 'Cancelado'),
    ]

    TIPO_DOC_CHOICES = [
        ('CC',        'Cédula de Ciudadanía'),
        ('TI',        'Tarjeta de Identidad'),
        ('CE',        'Cédula de Extranjería'),
        ('Pasaporte', 'Pasaporte'),
    ]

    numero_turno     = models.CharField(max_length=20, unique=True, blank=True)
    cliente          = models.ForeignKey(
                           Usuario, on_delete=models.CASCADE,
                           related_name='turnos_como_cliente',
                           verbose_name='Cliente')
    empleado         = models.ForeignKey(
                           Usuario, on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='turnos_como_empleado',
                           verbose_name='Empleado')
    tipo_documento   = models.CharField(max_length=20, choices=TIPO_DOC_CHOICES, verbose_name='Tipo de documento')
    numero_documento = models.CharField(max_length=30, verbose_name='Número de documento')
    motivo           = models.CharField(max_length=200, verbose_name='Motivo')
    fecha            = models.DateField(verbose_name='Fecha')
    hora             = models.CharField(max_length=5, verbose_name='Hora')
    estado           = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente', verbose_name='Estado')
    llamado          = models.BooleanField(default=False, verbose_name='Llamado')
    llamado_en       = models.DateTimeField(null=True, blank=True, verbose_name='Llamado en')
    creado_en        = models.DateTimeField(auto_now_add=True)
    actualizado_en   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.numero_turno} — {self.cliente}'

    def save(self, *args, **kwargs):
        if not self.numero_turno:
            self.numero_turno = self._generar_numero()
        super().save(*args, **kwargs)

    def _generar_numero(self):
        while True:
            codigo = 'T-' + ''.join(random.choices(string.digits, k=4))
            if not Turno.objects.filter(numero_turno=codigo).exists():
                return codigo