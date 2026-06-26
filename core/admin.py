from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Company, Usuario, Turno

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'nit', 'created_at']
    search_fields = ['name', 'nit']

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ['username', 'email', 'company', 'rol', 'is_staff', 'is_superuser']
    list_filter = ['company', 'rol', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Información SaaS Multi-Tenant', {'fields': ('company', 'rol', 'tipo_documento', 'numero_documento')}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.company:
            # Los admin de empresa solo gestionan usuarios de su propio tenant
            return qs.filter(company=request.user.company)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.company = request.user.company
        super().save_model(request, obj, form, change)


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ['numero_turno', 'company', 'cliente', 'empleado', 'fecha', 'hora', 'estado']
    list_filter = ['company', 'estado', 'fecha']
    search_fields = ['numero_turno', 'cliente__username', 'empleado__username']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.company = request.user.company
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Garantiza que en el Django Admin no se puedan elegir
        clientes o empleados de otros tenants.
        """
        if not request.user.is_superuser:
            if db_field.name == "cliente":
                kwargs["queryset"] = Usuario.objects.filter(company=request.user.company, rol="cliente")
            if db_field.name == "empleado":
                kwargs["queryset"] = Usuario.objects.filter(company=request.user.company, rol="empleado")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)