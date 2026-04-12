from django.urls import path
from . import views

urlpatterns = [

    # ── Auth ──
    path('',        views.login_view,  name='login'),
    path('login/',  views.login_view,  name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),

    # ── Dashboard admin ──
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── Turnos ──
    path('turnos/',              views.turnos_lista,    name='turnos_lista'),
    path('turnos/crear/',        views.turno_crear,     name='turno_crear'),
    path('turnos/<int:pk>/editar/',   views.turno_editar,    name='turno_editar'),
    path('turnos/<int:pk>/eliminar/', views.turno_eliminar,  name='turno_eliminar'),
    path('turnos/pdf/',          views.turnos_pdf,      name='turnos_pdf'),

    # ── Usuarios ──
    path('usuarios/',                    views.usuarios_lista,   name='usuarios_lista'),
    path('usuarios/crear/',              views.usuario_crear,    name='usuario_crear'),
    path('usuarios/<int:pk>/editar/',    views.usuario_editar,   name='usuario_editar'),
    path('usuarios/<int:pk>/eliminar/',  views.usuario_eliminar, name='usuario_eliminar'),
    path('usuarios/pdf/',                views.usuarios_pdf,     name='usuarios_pdf'),

    # ── Panel cliente ──
    path('cliente/', views.cliente_panel, name='cliente_panel'),

    # ── Panel empleado ──
    path('empleado/', views.empleado_panel, name='empleado_panel'),

    # ── Llamar turno / notificaciones ──
    path('turnos/<int:pk>/llamar/',    views.llamar_turno,         name='llamar_turno'),
    path('turnos/verificar-llamado/',  views.verificar_llamado,    name='verificar_llamado'),
    path('turnos/<int:pk>/estado/',    views.cambiar_estado_turno, name='cambiar_estado_turno'),
]