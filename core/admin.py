from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Turno


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display  = ['username', 'first_name', 'last_name', 'email', 'rol', 'date_joined']
    list_filter   = ['rol']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets     = UserAdmin.fieldsets + (
        ('Rol TurnoFácil', {'fields': ('rol',)}),
    )


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display  = ['numero_turno', 'cliente', 'empleado', 'fecha', 'hora', 'estado']
    list_filter   = ['estado', 'fecha']
    search_fields = ['numero_turno', 'numero_documento', 'cliente__first_name']
    date_hierarchy = 'fecha'