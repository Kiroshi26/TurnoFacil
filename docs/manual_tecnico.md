# Manual Técnico — TurnoFácil
**Sistema de Gestión de Turnos**

* **Versión**: 1.0
* **Fecha**: Junio 2026
* **Autor**: Equipo TurnoFácil
* **Tecnología**: Python 3.x · Django 6.0.3 · SQLite 3 (Dev) / MariaDB (Prod)

---

## 1. Información General del Proyecto
TurnoFácil es una aplicación web monolítica desarrollada con el framework Django (Python). Implementa el patrón MVT (Model-View-Template) y utiliza el ORM nativo de Django para la persistencia de datos. Permite gestionar de manera digital el ciclo completo de turnos (creación, edición, eliminación, llamado del cliente e indicación de estado de atención) clasificado en tres perfiles de usuario: Administrador, Empleado y Cliente.

### Características Clave:
- Autenticación segura personalizada por correo electrónico (EmailBackend).
- Ciclo de restablecimiento de contraseña vinculado a Django Auth.
- Dashboard administrativo integrado con gráfico de barras estadísticas (Chart.js) y KPIs en tiempo real alineados con la zona horaria local (`America/Bogota`).
- Generación de reportes PDF estructurados con filtros mediante ReportLab.
- Polling en tiempo real para llamado visual y sonoro del cliente en espera.
- Formulario de edición de perfil de usuario integrado directamente al avatar/user-card de la barra lateral.
- Interfaz moderna en modo oscuro (Slate/Indigo) con diseño minimalista para acciones críticas.

---

## 2. Arquitectura del Sistema
El sistema emplea una arquitectura monolítica basada en el patrón MVT de Django. Las solicitudes HTTP se procesan por la pila de middleware y enrutamiento, pasando por filtros de decoradores de roles, lógica de vistas y se devuelve una respuesta HTML completa o JSON (para AJAX).

### Diagrama de Flujo MVT:
```
 NAVEGADOR (HTTP/HTTPS)
  │
  ▼
 +─────────────────────────────────────────────────────────────+
 │ Django WSGI / ASGI (manage.py runserver / Gunicorn)          │
 +─────────────────────────────────────────────────────────────+
  │
  ▼
 +──────────────────+      +─────────────────+
 │ Middleware Stack │      │ Archivos Static │
 │ (CSRF, Auth, Sec)│      │ (CSS, JS, IMG)  │
 +──────────────────+      +─────────────────+
  │
  ▼
 +─────────────────────────────────────────────────────────────+
 │ URL Router (turnofacil/urls.py -> core/urls.py)             │
 +─────────────────────────────────────────────────────────────+
  │
  ▼
 +─────────────────────────────────────────────────────────────+
 │ Decoradores de Acceso (@login_requerido, @solo_admin, etc.)  │
 +─────────────────────────────────────────────────────────────+
  │
  ▼
 +─────────────────────────────────────────────────────────────+
 │ VIEWS / VISTAS (core/views.py)                              │
 +─────────────────────────────────────────────────────────────+
  │                          │
  ▼                          ▼
 +───────────────+          +─────────────────+
 │ MODELS (ORM)  │          │ FORMS           │
 │ (core/models) │          │ (Validaciones)  │
 +───────────────+          +─────────────────+
  │                          │
  ▼                          ▼
 +─────────────────────────────────────────────────────────────+
 │ BASE DE DATOS (SQLite 3 / MariaDB 10.6+)                     │
 +─────────────────────────────────────────────────────────────+
  │
  ▼
 +─────────────────────────────────────────────────────────────+
 │ TEMPLATES (JTL / HTML con DTL)                              │
 +─────────────────────────────────────────────────────────────+
  │
  ▼
 RESPUESTA HTML / JSON al navegador
```

---

## 3. Tecnologías Utilizadas
- **Python (3.10+)**: Lenguaje de programación base.
- **Django (6.0.3)**: Framework de desarrollo web.
- **SQLite 3**: Base de datos ligera para desarrollo y pruebas.
- **MariaDB 10.6+**: Base de datos de producción relacional.
- **ReportLab (4.x)**: Biblioteca para la generación dinámica de archivos PDF.
- **Chart.js (4.4.1)**: Renderizado de la gráfica estadística de turnos.
- **Bootstrap Icons (1.11.3)**: Catálogo de iconos vectoriales para el front-end.
- **Tipografías**: Google Fonts (DM Sans y DM Mono) integradas en el front-end.

---

## 4. Requisitos del Sistema
- **RAM Mínima**: 512 MB (Desarrollo) / 2 GB (Producción recomendado).
- **CPU Mínima**: 1 Núcleo (Desarrollo) / 2 Núcleos (Producción).
- **Espacio de Disco**: 500 MB libres para logs y base de datos local.
- **SO Recomendado**: Linux Ubuntu 20.04+ (Producción).

---

## 5. Instalación y Configuración

### 5.1 Crear Entorno Virtual e Instalar Dependencias:
```powershell
python -m venv venv
# Activar entorno (Windows)
venv\Scripts\activate
# Activar entorno (Linux/Mac)
source venv/bin/activate

# Instalar dependencias requeridas
pip install django reportlab mysqlclient python-decouple
```

### 5.2 Base de Datos de Producción (settings.py):
Reemplazar el bloque `DATABASES` para conectar a MariaDB/MySQL:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'turnofacil',
        'USER': 'turnofacil_user',
        'PASSWORD': 'tu_contraseña_segura',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
```

### 5.3 Aplicar Migraciones y Crear Superusuario:
```powershell
python manage.py migrate
python manage.py createsuperuser
# Ingresa: username, email, password
```

### 5.4 Servidor de Correo (settings.py):
TurnoFácil soporta doble configuración (consola para desarrollo y SMTP para producción):
```python
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend' if os.environ.get('EMAIL_HOST') else 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'TurnoFácil <no-reply@turnofacil.com>')
```

---

## 6. Modelo de Base de Datos

### Tabla `core_usuario`
- `id` (BIGINT, PK): Autoincremental.
- `username` (VARCHAR 150, UNIQUE): Nombre de usuario.
- `email` (VARCHAR 254, UNIQUE): Correo de acceso.
- `password` (VARCHAR 128): Contraseña hasheada.
- `first_name` (VARCHAR 150): Nombre de usuario (Límite form: 100, solo letras).
- `last_name` (VARCHAR 150): Apellido (Límite form: 100, solo letras).
- `rol` (VARCHAR 20): Enum (admin, empleado, cliente).
- `tipo_documento` (VARCHAR 20, Null): Enum (CC, TI, CE, Pasaporte).
- `numero_documento` (VARCHAR 30, Null): Documento (Límite form: 30, solo dígitos).

### Tabla `core_turno`
- `id` (BIGINT, PK): Autoincremental.
- `numero_turno` (VARCHAR 20, UNIQUE): Código único auto-generado (T-XXXX).
- `cliente_id` (BIGINT, FK -> core_usuario, CASCADE): Relación con cliente.
- `empleado_id` (BIGINT, FK -> core_usuario, SET_NULL, Null): Relación con empleado asignado.
- `tipo_documento` (VARCHAR 20): Tipo de documento usado en el turno.
- `numero_documento` (VARCHAR 30): Número de documento.
- `motivo` (VARCHAR 200): Razón de la cita.
- `fecha` (DATE): Fecha reservada.
- `hora` (VARCHAR 5): Franja horaria de la reserva (ej: "08:30").
- `estado` (VARCHAR 20): Enum (Pendiente, Atendido, Cancelado).
- `llamado` (BOOLEAN): Estado del polling del cliente (True si el empleado lo llama).
- `llamado_en` (DATETIME, Null): Timestamp del momento de llamado.

---

## 7. Estructura de Rutas (Endpoints Principales)

### 7.1 Módulo de Autenticación y Perfil
- `GET/POST` `/login/`: Inicio de sesión (`login_view`).
- `GET/POST` `/registro/`: Creación de cliente (`registro_view`).
- `GET` `/logout/`: Cierre de sesión (`logout_view`).
- `GET/POST` `/perfil/`: Edición de información del perfil (`editar_perfil`).
- `GET/POST` `/password-reset/`: Formulario de solicitud de token de restablecimiento.
- `GET/POST` `/password-reset-confirm/<uidb64>/<token>/`: Enlace de asignación de nueva contraseña.

### 7.2 Gestión de Turnos
- `GET` `/turnos/`: Lista completa de turnos en modo admin (`turnos_lista`).
- `GET/POST` `/turnos/crear/`: Creación de turno (`turno_crear`).
- `GET/POST` `/turnos/<pk>/editar/`: Modificar turno (`turno_editar`).
- `POST` `/turnos/<pk>/eliminar/`: Eliminar turno (`turno_eliminar`).
- `GET` `/turnos/pdf/`: Exportación a PDF de turnos (`turnos_pdf`).
- `POST` `/turnos/<pk>/llamar/`: Endpoint JSON para llamar al cliente (`llamar_turno`).
- `GET` `/turnos/verificar-llamado/`: Polling cliente (`verificar_llamado`).

---

## 8. Seguridad del Sistema
1. **Control de Acceso por Roles (Decoradores)**:
   - `@login_requerido`: Valida sesión activa.
   - `@solo_admin`: Bloquea accesos a empleados o clientes en paneles de administración.
   - `@solo_empleado` y `@solo_cliente`: Restringe funciones del panel del módulo respectivo.
2. **Protección CSRF**:
   - Middleware `CsrfViewMiddleware` habilitado globalmente.
   - Formulario e interacciones JavaScript (`fetch`) configuran el encabezado `X-CSRFToken` a partir de cookies.
3. **Validación de Datos en Formularios**:
   - Validación restrictiva de nombres (solo letras y espacios) y documento (solo números).
   - Longitudes máximas estrictas a nivel de formulario para evitar desbordamiento o inyección de datos de gran volumen.
