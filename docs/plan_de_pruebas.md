# Plan de Pruebas del Sistema — TurnoFácil

Este documento define el plan de pruebas del sistema TurnoFácil para validar la calidad, seguridad, desempeño y funcionalidad del software bajo condiciones normales y extremas.

---

## 1. Introducción
Este plan de pruebas sistemático asegura el correcto funcionamiento de los módulos de TurnoFácil (autenticación por correo electrónico, asignación de turnos, llamado de turnos, generación de reportes y dashboard), así como los controles de seguridad de acceso por rol y la corrección de vulnerabilidades críticas antes del despliegue en producción.

---

## 2. Objetivos del Plan de Pruebas
- **Pruebas Unitarias**: Validar de manera aislada modelos, formularios, decoradores y el backend de autenticación.
- **Pruebas de Integración**: Validar los flujos completos de interacción de la base de datos con las vistas y plantillas HTML.
- **Pruebas de Seguridad**: Garantizar que el control de acceso por rol bloquee accesos indebidos e invalidar el uso de credenciales expuestas.
- **Pruebas de Desempeño (Carga y Estrés)**: Evaluar el comportamiento de SQLite y establecer límites de concurrencia previos a la migración a MariaDB.

---

## 3. Alcance y Entorno de Pruebas

### Incluido en las pruebas:
- Autenticación personalizada (correo y contraseña), recuperación de contraseña y edición del perfil.
- CRUD completo de turnos y usuarios por rol (Admin, Empleado, Cliente).
- Polling y llamados de turnos integrados con el correo y sonido de alerta visual.
- Exportaciones en formato PDF (ReportLab) con filtros aplicados.
- Dashboard de estadísticas en base a la fecha local del usuario.

### Especificaciones del Entorno:
- **SO**: Windows 10/11 (desarrollo) · Ubuntu 22.04 LTS (producción)
- **Lenguaje / Framework**: Python 3.14 · Django 6.0.3 (MVT)
- **Base de Datos**: SQLite (desarrollo/pruebas) · MariaDB 10.6+ (producción)
- **Servidor de Producción**: Gunicorn + Nginx como proxy reverso.
- **Correo**: console.EmailBackend (desarrollo) · SMTP Gmail/SendGrid (producción).

---

## 4. Estrategia y Cobertura de Pruebas
Las pruebas unitarias y de integración se ejecutan de manera automatizada utilizando la suite de pruebas de Django:
```powershell
python manage.py test core
```
* **Cobertura objetivo**: Mínimo 80% de las líneas en `models.py`, `forms.py`, `backends.py` y `decorators.py`.

---

## 5. Casos de Prueba (CP01 - CP77)

### 5.1 Autenticación y Sesiones
- **CP01 (Unitaria)**: Autenticar usuario con correo y contraseña válidos vía `EmailBackend`. *Esperado*: Retorna el usuario y establece la sesión. **[PASADO]**
- **CP02 (Unitaria)**: Autenticar con correo en mayúsculas (case-insensitive). *Esperado*: Retorna el usuario correctamente. **[PASADO]**
- **CP03 (Unitaria)**: Autenticar con contraseña incorrecta. *Esperado*: Retorna `None`, no inicia sesión. **[PASADO]**
- **CP04 (Unitaria)**: Autenticar con email no existente en la base de datos. *Esperado*: Retorna `None` sin lanzar excepciones. **[PASADO]**
- **CP05 (Integración)**: POST `/login/` con credenciales válidas de administrador. *Esperado*: Redirige a `/dashboard/`.
- **CP06 (Integración)**: POST `/login/` con credenciales válidas de empleado. *Esperado*: Redirige a `/empleado/`.
- **CP07 (Integración)**: POST `/login/` con credenciales válidas de cliente. *Esperado*: Redirige a `/cliente/`.
- **CP08 (Integración)**: POST `/login/` con contraseña incorrecta. *Esperado*: Permanece en login y muestra mensaje de error.
- **CP09 (Integración)**: GET `/login/` con usuario ya autenticado. *Esperado*: Redirige al panel correspondiente sin mostrar el login.
- **CP10 (Integración)**: GET `/logout/` - cerrar sesión. *Esperado*: Redirige a `/login/` y destruye la sesión.

### 5.2 Registro de Usuarios (Clientes)
- **CP11 (Unitaria)**: Validar campo `first_name` con caracteres numéricos (ej. 'Juan1'). *Esperado*: Formulario inválido con error de validación. **[PASADO]**
- **CP12 (Unitaria)**: Validar campo `numero_documento` con letras (ej. 'ABC123'). *Esperado*: Formulario inválido con error de validación. **[PASADO]**
- **CP13 (Unitaria)**: Validar que un email duplicado sea rechazado en `RegistroForm`. *Esperado*: Formulario inválido; email ya en uso.
- **CP14 (Integración)**: POST `/registro/` con todos los campos válidos. *Esperado*: Creación de usuario en BD y login automático. **[PASADO]**
- **CP15 (Integración)**: POST `/registro/` especificando el backend explícito. *Esperado*: Inicio de sesión exitoso sin `ValueError`. **[PASADO]**
- **CP16 (Integración)**: POST `/registro/` con email ya existente. *Esperado*: Formulario inválido, no duplica usuario.
- **CP17 (Integración)**: POST `/registro/` con password de confirmación incorrecta. *Esperado*: Muestra error de coincidencia.

### 5.3 Gestión de Turnos — Administrador
- **CP18 (Unitaria)**: Crear turno sin `numero_turno`. *Esperado*: Genera código único `T-\d{4}` en `save()`.
- **CP19 (Unitaria)**: Intentar generar número ya existente (colisión). *Esperado*: Bucle reintenta y genera un código alternativo.
- **CP20 (Integración)**: GET `/turnos/` autenticado como admin. *Esperado*: Retorna lista completa de turnos.
- **CP21 (Integración)**: GET `/turnos/?q=Juan`. *Esperado*: Filtra la lista por el nombre del cliente.
- **CP22 (Integración)**: GET `/turnos/?estado=Pendiente`. *Esperado*: Filtra turnos en estado pendiente.
- **CP23 (Integración)**: POST `/turnos/crear/` como admin con datos válidos. *Esperado*: Turno creado en BD y redirige a la lista.
- **CP24 (Integración)**: POST `/turnos/crear/` con fecha anterior a hoy. *Esperado*: Inválido: "La fecha no puede ser en el pasado".
- **CP25 (Integración)**: POST `/turnos/crear/` con hora ya pasada para el día de hoy. *Esperado*: Inválido, muestra mensaje de hora mínima.
- **CP26 (Integración)**: POST `/turnos/<pk>/editar/` como administrador. *Esperado*: Actualiza datos y redirige.
- **CP27 (Integración)**: POST `/turnos/<pk>/eliminar/` como admin. *Esperado*: Elimina el turno de la base de datos.
- **CP28 (Integración)**: POST `/turnos/<pk>/estado/` vía AJAX. *Esperado*: Retorna JSON `{ok: true, estado: 'Atendido'}`.
- **CP29 (Integración)**: GET `/turnos/pdf/` sin filtros. *Esperado*: Retorna respuesta HTTP PDF completa.
- **CP30 (Integración)**: GET `/turnos/pdf/?estado=Atendido`. *Esperado*: Retorna PDF con turnos filtrados.

### 5.4 Gestión de Turnos — Cliente
- **CP31 (Integración)**: GET `/cliente/` con cliente autenticado. *Esperado*: Muestra panel personal, turnos e historial.
- **CP32 (Integración)**: POST `/turnos/crear/` como cliente. *Esperado*: Toma tipo y número de documento preestablecidos en el perfil.
- **CP33 (Integración)**: POST `/turnos/crear/` como cliente. *Esperado*: Los campos de documento están ocultos (`HiddenInput`).
- **CP34 (Integración)**: POST `/turnos/<pk>/editar/` como cliente. *Esperado*: Permite modificar únicamente hora y empleado asignado.
- **CP35 (Integración)**: POST `/turnos/<pk>/editar/` de otro cliente. *Esperado*: Redirige a `/cliente/` con mensaje de error de permisos.
- **CP36 (Integración)**: POST `/turnos/<pk>/eliminar/` de otro cliente. *Esperado*: Redirige a `/cliente/` con error de permisos.
- **CP37 (Integración)**: GET `/turnos/verificar-llamado/` cuando el turno del cliente fue llamado. *Esperado*: Retorna `{llamado: true}` y actualiza el estado.
- **CP38 (Integración)**: GET `/turnos/verificar-llamado/` sin turnos llamados. *Esperado*: Retorna `{llamado: false}`.

### 5.5 Gestión de Turnos — Empleado
- **CP39 (Integración)**: GET `/empleado/` autenticado como empleado. *Esperado*: Muestra turnos asignados y botón de llamado.
- **CP40 (Integración)**: POST `/turnos/<pk>/llamar/` como empleado asignado. *Esperado*: Turno marcado `llamado=True`, registra `llamado_en`. **[PASADO]**
- **CP41 (Integración)**: POST `/turnos/<pk>/llamar/` y verificar envío de correo. *Esperado*: Envía un correo estructurado al cliente registrado. **[PASADO]**
- **CP42 (Integración)**: POST `/turnos/<pk>/llamar/` como empleado NO asignado. *Esperado*: Retorna error 404.
- **CP43 (Integración)**: POST `/turnos/<pk>/editar/` como empleado. *Esperado*: Permite editar fecha, hora, empleado y estado.

### 5.6 Gestión de Usuarios — Administrador
- **CP44 (Unitaria)**: Método `is_admin()` en usuario con rol='admin'. *Esperado*: Retorna `True`.
- **CP45 (Unitaria)**: Método `is_cliente()` en usuario con rol='empleado'. *Esperado*: Retorna `False`.
- **CP46 (Integración)**: GET `/usuarios/` autenticado como admin. *Esperado*: Muestra lista completa de usuarios.
- **CP47 (Integración)**: GET `/usuarios/?q=maria`. *Esperado*: Filtra usuarios que contengan "maria" en nombre o correo.
- **CP48 (Integración)**: POST `/usuarios/crear/` con datos válidos. *Esperado*: Usuario creado con contraseña hasheada de manera segura.
- **CP49 (Integración)**: POST `/usuarios/<pk>/editar/` dejando contraseña vacía. *Esperado*: Mantiene la contraseña actual sin sobreescribirla.
- **CP50 (Integración)**: POST `/usuarios/<pk>/eliminar/` a sí mismo. *Esperado*: Bloquea la eliminación y muestra error.
- **CP51 (Integración)**: GET `/usuarios/pdf/`. *Esperado*: Genera y descarga el PDF de los usuarios del sistema.

### 5.7 Dashboard — Administrador
- **CP52 (Integración)**: GET `/dashboard/` autenticado como admin. *Esperado*: Muestra los KPIs (Usuarios, Turnos, Pendientes, Atendidos) sincronizados con la base de datos.
- **CP53 (Integración)**: GET `/dashboard/` comprueba que la gráfica contiene 7 días usando la fecha local. *Esperado*: Array de 7 etiquetas (ej. 'Lun 8' a 'Dom 14') sin desajustes por desfase UTC.
- **CP54 (Integración)**: GET `/dashboard/` comprueba límite de turnos recientes. *Esperado*: Lista un máximo de 5 turnos ordenados por creación.

### 5.8 Control de Acceso por Rol (Seguridad)
- **CP55 (Seguridad)**: GET `/dashboard/` sin autenticación. *Esperado*: Redirige a `/login/`.
- **CP56 (Seguridad)**: GET `/dashboard/` autenticado como empleado. *Esperado*: Acceso denegado (Retorna 403).
- **CP57 (Seguridad)**: GET `/dashboard/` autenticado como cliente. *Esperado*: Acceso denegado (Retorna 403).
- **CP58 (Seguridad)**: GET `/usuarios/` autenticado como empleado. *Esperado*: Acceso denegado (Retorna 403).
- **CP59 (Seguridad)**: GET `/usuarios/` autenticado como cliente. *Esperado*: Acceso denegado (Retorna 403).
- **CP60 (Seguridad)**: GET `/cliente/` autenticado como admin. *Esperado*: Acceso denegado (Retorna 403).
- **CP61 (Seguridad)**: GET `/empleado/` autenticado como cliente. *Esperado*: Acceso denegado (Retorna 403).
- **CP62 (Seguridad)**: POST `/turnos/<pk>/llamar/` autenticado como cliente. *Esperado*: Acceso denegado (Retorna 403).
- **CP63 (Seguridad)**: POST `/turnos/<pk>/estado/` autenticado como empleado. *Esperado*: Acceso denegado (Retorna 403).

### 5.9 Vulnerabilidades Críticas
- **CP64 (Seguridad)**: Verificar que `SECRET_KEY` provenga de variable de entorno y no esté expuesta de forma estática. *Esperado*: `settings.SECRET_KEY != 'django-insecure...'`.
- **CP65 (Seguridad)**: Verificar que `db.sqlite3` esté agregada a `.gitignore`. *Esperado*: El archivo no se incluye en el repositorio.
- **CP66 (Seguridad)**: Verificar que `ALLOWED_HOSTS` esté configurada adecuadamente en producción. *Esperado*: No permite comodín `*`.
- **CP67 (Seguridad)**: Intentar descargar `db.sqlite3` de forma pública por URL. *Esperado*: El servidor responde 404 o 403.
- **CP68 (Seguridad)**: Intentar acceder a `/admin/` sin credenciales de superusuario. *Esperado*: Redirige al login de administración.

### 5.10 Pruebas de Carga (Locust / Apache JMeter)
- **CP69 (Carga)**: 20 usuarios simultáneos haciendo GET `/login/`. *Esperado*: Tiempo de respuesta < 1 segundo, sin errores.
- **CP70 (Carga)**: 20 clientes simultáneos haciendo POST `/turnos/crear/`. *Esperado*: Creación de turnos sin errores 500.
- **CP71 (Carga)**: 10 empleados simultáneos llamando turnos. *Esperado*: Correos encolados o enviados, sin errores en JSON.
- **CP72 (Carga)**: 50 usuarios de diferentes perfiles navegando simultáneamente durante 5 minutos. *Esperado*: Respuesta < 3 segundos, tasa de error < 2%.
- **CP73 (Carga)**: 20 descargas de PDF simultáneas. *Esperado*: Descarga correcta, sin timeouts en la base de datos.

### 5.11 Pruebas de Estrés
- **CP74 (Estrés)**: Escalar concurrencia de 100 a 300 usuarios en pasos de 50 cada 30 segundos. *Esperado*: Registrar punto de degradación de velocidad.
- **CP75 (Estrés)**: 500 intentos de inicio de sesión simultáneos. *Esperado*: El servidor responde (con error controlado) sin crash del proceso.
- **CP76 (Estrés)**: Reducir la carga de 300 a 10 usuarios tras pico de estrés. *Esperado*: Recuperación del tiempo de respuesta (< 2 segundos) sin intervención manual.
- **CP77 (Estrés)**: Verificar la integridad de base de datos tras la sesión de estrés. *Esperado*: No se encuentran números de turnos duplicados.

---

## 6. Criterios de Aceptación
- Cobertura de pruebas unitarias y de integración aprobadas: `>= 90%`.
- Tiempo de respuesta promedio en condiciones normales: `< 2 segundos`.
- Cero vulnerabilidades críticas abiertas (CP64-CP68 aprobados al 100%).
- Bug de inicio de sesión de registro corregido sin regresión.
