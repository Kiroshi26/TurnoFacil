# Reporte de Bugs e Incidencias — TurnoFácil

Este documento resume el estado de los bugs reportados en el sistema de gestión de turnos TurnoFácil, detallando su severidad, descripción, impacto y la solución aplicada o propuesta.

---

## 📋 Resumen de Incidencias

| ID Bug | Caso Relacionado | Descripción | Severidad | Estado Actual |
| :--- | :--- | :--- | :--- | :--- |
| **BUG-001** | CP-007 / CP-015 | ValueError al registrar usuario: múltiples backends de autenticación sin especificar explícito. | **Alta** | **Resuelto** |
| **BUG-002** | CP-011 | Al crear un turno, el cliente siempre queda asignado como el usuario autenticado (independiente del rol). | **Media** | **Abierto** |
| **BUG-003** | CP-025 | Error de correo no manejado silenciosamente en `llamar_turno` rompe el flujo JSON. | **Media** | **Resuelto** |
| **BUG-004** | CP-011 | Race condition en la generación de `numero_turno` en `_generar_numero()`. | **Media** | **Abierto** |
| **BUG-005** | CP-015 | Ausencia de paginación en todas las vistas de lista. | **Baja** | **Abierto** |
| **BUG-006** | CP-011 | El campo `hora` se almacena como `CharField` en lugar de `TimeField`. | **Baja** | **Abierto** |
| **BUG-007** | CP-53 / CP-37 | Desajuste de zona horaria (UTC vs Local) en filtros de fecha. | **Alta** | **Resuelto** |
| **BUG-008** | CP-15 / CP-41 | Corrupción del link de recuperación de contraseña por codificación `quoted-printable` en consola. | **Media** | **Resuelto** |

---

## 🔍 Detalle de Incidencias y Soluciones

### BUG-001: ValueError al registrar usuario (Múltiples Backends)
* **Descripción**: Al llamar a `login(request, user)` tras el registro, Django lanza `ValueError: 'You have multiple authentication backends configured...'` al no saber qué backend utilizar.
* **Impacto**: Bloquea el flujo de registro de clientes en producción, causando error 500.
* **Solución Aplicada**: Se especificó el backend explícitamente en la llamada a `login()` dentro de `registro_view` y `login_view`:
  ```python
  login(request, user, backend='core.backends.EmailBackend')
  ```

### BUG-002: Cliente asignado incorrectamente al crear turno (Admin/Empleado)
* **Descripción**: En `turno_crear`, la línea `turno.cliente = user` asigna el usuario autenticado como cliente del turno. Si un administrador o empleado crea el turno para un cliente externo, el creador queda como cliente.
* **Impacto**: Los turnos quedan mal asignados e impide que el módulo administrativo registre turnos correctamente para los clientes.
* **Solución Propuesta**: Modificar `TurnoForm` y `turno_crear` para exponer un campo de selección del cliente destino para los roles `admin` y `empleado`, asignando este cliente seleccionado en vez del `request.user`.

### BUG-003: Error de correo no manejado en llamado de turno
* **Descripción**: Si falla el servidor de correo al llamar un turno (por ejemplo, por problemas de SMTP), la excepción no se captura a nivel superior y rompe la respuesta JSON del endpoint `llamar_turno`.
* **Impacto**: Retorna un error 500 al empleado, bloqueando el sistema visual de llamados.
* **Solución Aplicada**: Se envolvió la función `send_mail` dentro de un bloque `try/except Exception as mail_error` que registra el error en `logger.error` pero permite continuar, garantizando que el cambio de estado del turno persista y responda exitosamente.

### BUG-004: Race condition en la generación de número de turno
* **Descripción**: `_generar_numero()` verifica la unicidad con un bucle `while` usando `filter().exists()` sobre SQLite, sin control transaccional o atómico.
* **Impacto**: Si dos solicitudes simultáneas generan el mismo número de turno antes de persistir, se genera un `IntegrityError` (violación de la restricción `UNIQUE`), interrumpiendo el flujo.
* **Solución Propuesta**: Envolver la lógica de `save()` con `@transaction.atomic` y usar `select_for_update()` en la consulta de unicidad, o migrar la clave a un formato robusto basado en marcas de tiempo con identificador atómico.

### BUG-005: Ausencia de paginación en vistas de lista
* **Descripción**: Las vistas `turnos_lista`, `usuarios_lista`, `cliente_panel` y `empleado_panel` cargan todos los registros del modelo a la vez.
* **Impacto**: Degradación del rendimiento de la base de datos y de la red cuando el sistema supera los 500 turnos creados.
* **Solución Propuesta**: Implementar paginación con `django.core.paginator.Paginator` en todas las vistas de listas de registros, limitando la carga a 20-50 registros por página.

### BUG-006: Campo 'hora' almacenado como CharField
* **Descripción**: El campo `hora` se definió en `Turno` como un `CharField(max_length=5)` en lugar de un `TimeField`.
* **Impacto**: Dificulta el ordenamiento cronológico a nivel de base de datos y las consultas de rangos de horas, y puede causar incoherencias de formato.
* **Solución Propuesta**: Migrar el campo `hora` a `models.TimeField` ajustando las plantillas con un selector `TimeInput` y sus validadores correspondientes.

### BUG-007: Desajuste de Zona Horaria (UTC vs Local)
* **Descripción**: El cálculo de la fecha del día actual usaba la fecha del servidor en UTC (`timezone.now().date()`). Al estar la aplicación en la zona horaria `America/Bogota` (UTC-5), el servidor consideraba que ya era el día siguiente después de las 7:00 PM local.
* **Impacto**: La gráfica de barras del dashboard mostraba 0 en el día actual (por desajuste de fecha) y los turnos activos de los clientes y empleados desaparecían o fallaban en el polling nocturno.
* **Solución Aplicada**: Se reemplazaron todas las llamadas de `timezone.now().date()` por `timezone.localtime(timezone.now()).date()` en las vistas y validadores de formularios para forzar consistencia horaria local.

### BUG-008: Corrupción del enlace de recuperación de contraseña (Consola)
* **Descripción**: El correo de recuperación contenía caracteres no ASCII (acentos, `ñ`, etc.). Al imprimirse en la consola de depuración de Django, se codificaba en `quoted-printable`, dividiendo las líneas largas e inyectando un signo `=` en la mitad del enlace de restablecimiento.
* **Impacto**: Cuando el usuario copiaba o daba clic al enlace desde su terminal, la URL quedaba corrupta y el token de recuperación fallaba.
* **Solución Aplicada**: Se optimizó la plantilla `password_reset_email.html` para usar exclusivamente caracteres ASCII en su texto. Al ser ASCII puro, el enlace se imprime de forma directa, continua y 100% copiable desde la consola.
