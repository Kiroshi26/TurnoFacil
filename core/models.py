from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import JSONField
from django.core.exceptions import ValidationError
import random
import string

class Company(models.Model):
    """
    Representa a cada empresa/inquilino (Tenant) del sistema SaaS.
    """
    name = models.CharField(max_length=150, unique=True, verbose_name="Nombre de la Empresa")
    nit = models.CharField(max_length=50, unique=True, verbose_name="NIT / Identificación")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Configuración dinámica (ej: {"slot_duration": 30, "opening_time": "08:00"})
    business_config = JSONField(
        default=dict, 
        blank=True, 
        help_text="Configuraciones dinámicas de negocio de la empresa."
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

    def __str__(self):
        return self.name


class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado.
    La relación con Company es opcional para dar soporte a Superusuarios globales.
    """
    ROL_CHOICES = [
        ('admin',    'Administrador de Empresa'),
        ('empleado', 'Empleado'),
        ('cliente',  'Cliente'),
    ]
    
    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='cliente')
    
    # FK opcional para permitir Superusuarios sin empresa asociada
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='usuarios',
        verbose_name="Empresa"
    )
    
    tipo_documento = models.CharField(max_length=20, blank=True, null=True)
    numero_documento = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        indexes = [
            models.Index(fields=['company', 'id']),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    def is_admin(self):
        return self.rol == 'admin'

    def is_empleado(self):
        return self.rol == 'empleado'

    def is_cliente(self):
        return self.rol == 'cliente'


class Turno(models.Model):
    """
    Representa las citas en el sistema de agendamiento.
    """
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Atendido',  'Atendido'),
        ('Cancelado', 'Cancelado'),
    ]

    numero_turno = models.CharField(max_length=20, unique=True, blank=True)
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='turnos',
        verbose_name="Empresa"
    )
    cliente = models.ForeignKey(
        Usuario, 
        on_delete=models.CASCADE, 
        related_name='turnos_como_cliente'
    )
    empleado = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='turnos_como_empleado'
    )
    
    tipo_documento = models.CharField(max_length=20)
    numero_documento = models.CharField(max_length=30)
    motivo = models.CharField(max_length=200)
    fecha = models.DateField()
    hora = models.CharField(max_length=5)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    llamado = models.BooleanField(default=False)
    llamado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        indexes = [
            models.Index(fields=['company', 'fecha']),
        ]

    def __str__(self):
        return f"{self.numero_turno} — {self.company.name}"

    def save(self, *args, **kwargs):
        if not self.numero_turno:
            self.numero_turno = self._generar_numero()
        super().save(*args, **kwargs)

    def _generar_numero(self):
        # 1. Obtener configuración de la empresa o detectar por nombre
        config = self.company.business_config if self.company else {}
        prefix = config.get('turno_prefix')
        start = config.get('turno_start')
        
        if not prefix or not start:
            # Detección por nombre de la empresa
            nombre = self.company.name.lower() if self.company else ""
            if 'claro' in nombre:
                prefix = 'C'
                start = 100
            elif 'movistar' in nombre:
                prefix = 'M'
                start = 200
            elif 'tigo' in nombre:
                prefix = 'T'
                start = 300
            else:
                prefix = self.company.name[0].upper() if self.company and self.company.name else 'T'
                start = 100
                
        # 2. Generar el número correlativo o secuencial
        # Encontrar el último número de turno de esta empresa que tenga el mismo prefijo
        prefix_pattern = f"{prefix}-"
        turnos_empresa = Turno.objects.filter(company=self.company, numero_turno__startswith=prefix_pattern)
        
        max_num = start - 1
        for t in turnos_empresa:
            try:
                num_part = int(t.numero_turno.split('-')[1])
                if num_part > max_num:
                    max_num = num_part
            except (IndexError, ValueError):
                continue
                
        next_num = max_num + 1
        return f"{prefix}-{next_num}"