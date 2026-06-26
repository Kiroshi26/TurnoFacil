# TurnoFácil — Sistema de Gestión de Turnos

TurnoFácil es una plataforma web desarrollada en Python con el framework **Django** que permite administrar la solicitud, asignación y llamado de turnos de atención al público de forma ágil y digital. El sistema cuenta con tres perfiles diferenciados: **Administrador**, **Empleado** y **Cliente**.

---

## 📚 Documentación del Proyecto

Hemos centralizado y actualizado toda la documentación del sistema con los últimos cambios y mejoras integradas:

1. **[Manual Técnico](file:///c:/turnofacil-django/docs/manual_tecnico.md)**: 
   * Detalla la arquitectura MVT del sistema.
   * Contiene el esquema detallado de la base de datos (Usuario y Turno).
   * Explica los endpoints principales, controles de seguridad (CSRF, contraseñas, roles) y los pasos de instalación, configuración y despliegue (Gunicorn/Nginx, SMTP, etc.).

2. **[Plan de Pruebas del Sistema](file:///c:/turnofacil-django/docs/plan_de_pruebas.md)**:
   * Describe la estrategia de aseguramiento de calidad (pruebas unitarias, integración, carga, estrés y seguridad).
   * Contiene los **77 casos de prueba** estructurados (`CP01` a `CP77`) y los criterios de aceptación y riesgos asociados al proyecto.

3. **[Plan de Capacitación](file:///c:/turnofacil-django/docs/plan_de_capacitacion.md)**:
   * Define la metodología práctica (hands-on) para la formación de los usuarios.
   * Detalla la agenda del entrenamiento técnico (12 horas estructuradas en 3 módulos) y de los usuarios finales (Administradores, Empleados y Clientes).

4. **[Reporte de Bugs e Incidencias](file:///c:/turnofacil-django/docs/reporte_bugs.md)**:
   * Registra y rastrea el estado de los bugs reportados (`BUG-001` a `BUG-008`).
   * Explica las correcciones ya implementadas (múltiples backends, manejo de correo, zona horaria y codificación del enlace de recuperación en terminal) y las soluciones propuestas para los bugs pendientes.

---

## ⚡ Guía Rápida de Inicio (Desarrollo)

1. **Crear y activar el entorno virtual**:
   ```powershell
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

2. **Instalar dependencias**:
   ```powershell
   pip install -r requirements.txt
   ```
   *(Si el archivo `requirements.txt` no está creado, puedes instalar de forma directa: `pip install django reportlab mysqlclient python-decouple`)*

3. **Ejecutar migraciones de la base de datos**:
   ```powershell
   python manage.py migrate
   ```

4. **Iniciar el servidor local**:
   ```powershell
   python manage.py runserver
   ```
   *La aplicación estará disponible en: `http://127.0.0.1:8000/`*

5. **Correr la suite de pruebas unitarias**:
   ```powershell
   python manage.py test core
   ```