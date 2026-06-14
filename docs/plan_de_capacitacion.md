# Plan de Capacitación — TurnoFácil

Este documento establece la metodología, el cronograma y los contenidos de capacitación para el equipo técnico y los usuarios finales del sistema de gestión de turnos TurnoFácil.

---

## 1. Introducción
Para asegurar el correcto funcionamiento, mantenimiento y adopción del sistema TurnoFácil, se establece un programa estructurado en dos grandes frentes:
1. **Capacitación Técnica**: Dirigida a desarrolladores, administradores de sistemas y encargados de operaciones de infraestructura.
2. **Capacitación de Usuario Final**: Dirigida a administradores de la organización, empleados que atienden público y clientes que solicitan turnos.

---

## 2. Objetivos de la Capacitación
- Habilitar al equipo técnico en la instalación, configuración y despliegue del sistema.
- Capacitar a los administradores en la administración de usuarios, monitoreo del dashboard y reportes PDF.
- Capacitar a los empleados en la gestión activa del llamado de clientes en tiempo real.
- Guiar a los clientes en el flujo de autorregistro, solicitud de turnos y edición de perfil.

---

## 3. Planificación del Programa

### 3.1 Capacitación Técnica
- **Participantes**: Desarrolladores Backend, DevOps, DBAs.
- **Duración Total**: 12 horas (divididas en 3 sesiones de 4 horas).
- **Prerrequisito**: Conocimientos básicos de Python, Django y base de datos SQL.
- **Modalidad**: Práctica guiada (hands-on) con acceso a entorno local y grabación.

### 3.2 Capacitación de Usuario Final
- **Administradores**: 4 horas (2 sesiones de 2 horas) — Práctica guiada sobre entorno de prueba.
- **Empleados**: 2 horas (1 sesión de 2 horas) — Demostración y simulación en vivo de llamados.
- **Clientes**: 1 hora (Autoinstructivo) — Video tutorial animado y manual resumido en PDF.

---

## 4. Estructura y Temario

### 4.1 Capacitación Técnica (12 Horas)

#### Módulo 1: Entorno de Desarrollo (4 Horas)
- Descarga del repositorio de TurnoFácil.
- Configuración de entornos virtuales Python 3.14 y dependencias (`requirements.txt`).
- Configuración de variables de entorno mediante archivos `.env` (gestión de `SECRET_KEY` y `DEBUG`).
- Inicialización de migraciones en SQLite y creación de superusuario.

#### Módulo 2: Base de Datos y Modelos (4 Horas)
- Explicación del modelo relacional (`Usuario` y `Turno`).
- Migraciones del sistema e historial de cambios en Django ORM.
- Restricciones de unicidad (evitar doble reserva de empleado para misma fecha y hora).
- Configuración de base de datos de producción MariaDB 10.6+ en `settings.py`.
- Procedimientos de Backup y Restauración de base de datos.

#### Módulo 3: Operaciones, Seguridad y Producción (4 Horas)
- Análisis e interpretación del archivo de logs `logs/errores.log`.
- Configuración de seguridad para producción (`ALLOWED_HOSTS`, desactivar `DEBUG`).
- Configuración de servidor de correo SMTP para el envío real de notificaciones y recuperación de contraseñas.
- Despliegue en servidor Linux mediante Gunicorn y Nginx como proxy reverso.
- Ejecución e interpretación de la suite de pruebas unitarias (`manage.py test`).

---

### 4.2 Capacitación de Usuario Final

#### Administradores (4 Horas)
- **Sesión 1 (2h)**:
  - Recorrido del Dashboard Administrativo, interpretación del gráfico de barras de turnos y KPIs.
  - CRUD completo de Usuarios: creación de empleados, asignación de roles y edición de contraseñas.
  - Exportación del listado general de usuarios en PDF.
- **Sesión 2 (2h)**:
  - CRUD de Turnos: filtrado, búsqueda, creación manual de turnos.
  - Modificación de estados del turno (Pendiente/Atendido/Cancelado) directamente en el dashboard.
  - Descarga de reportes de turnos filtrados en formato PDF.

#### Empleados (2 Horas - Sesión Única)
- Acceso al panel del empleado y revisión de la lista de turnos asignados para el día actual.
- Simulación de llamado de turno (uso del botón "Llamar", notificación sonora y validación de correo best-effort).
- Edición rápida de la fecha, hora, estado y empleado asignado de los turnos activos.
- Identificación y priorización del próximo cliente en espera.

#### Clientes (1 Hora - Autoinstructivo)
- Registro de cuenta completando el formulario de datos personales (con filtros automáticos en caliente para nombres y documento).
- Login con correo electrónico y restablecimiento de contraseña usando el link de recuperación.
- Solicitud de turno rellenando motivo, fecha (máximo a 7 días) y hora.
- Consulta de panel personal para ver historial de turnos y estado actual.
- Recepción de alerta en pantalla en tiempo real cuando el empleado llama al turno.
- Edición y cancelación de sus propios turnos en espera.

---

## 5. Mecanismo de Evaluación y Aprobación
- **Técnica**: Lista de verificación para corroborar que cada participante tiene un entorno local levantado y ha ejecutado migraciones y pruebas con 100% de éxito.
- **Administrador / Empleado**: Prueba práctica e independiente que consiste en registrar un usuario, asignar un turno, procesar el llamado, exportar el PDF y cambiar el estado del turno sin asistencia.
- **Cliente**: Breve cuestionario digital de 5 preguntas sobre la solicitud y cancelación de turnos, exigiendo un mínimo de 4 respuestas correctas.
