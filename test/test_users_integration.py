from django.test import TestCase
from django.utils import timezone
from django.core import mail
from django.urls import reverse
from core.models import Usuario, Turno, Company


class AuthAndProfileTestCase(TestCase):
    """
    Integration tests for user authentication (registration, login, logout, password resets)
    and profile management.
    """
    def setUp(self):
        self.company = Company.objects.create(name='Empresa Claro Integration', nit='900.111.111-9')
        self.user = Usuario.objects.create_user(
            username='perfil_user',
            email='perfil@test.com',
            password='password123',
            rol='cliente',
            tipo_documento='CC',
            numero_documento='98765432',
            company=self.company
        )

    def test_registro_page_loads(self):
        """Verify the user registration page renders successfully."""
        response = self.client.get(reverse('registro'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/registro.html')

    def test_password_reset_request_sends_email(self):
        """Verify requesting a password reset triggers email dispatch with token."""
        response = self.client.post(reverse('password_reset'), {'email': 'perfil@test.com'})
        self.assertEqual(response.status_code, 302)  # Redirects to done page
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['perfil@test.com'])
        self.assertIn('password-reset-confirm', email.body)

    def test_editar_perfil_requires_login(self):
        """Verify unauthorized guests are redirected from profile editor."""
        response = self.client.get(reverse('editar_perfil'))
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_editar_perfil_update(self):
        """Verify users can successfully modify profile credentials."""
        self.client.login(email='perfil@test.com', password='password123')
        response = self.client.post(reverse('editar_perfil'), {
            'first_name': 'NuevoNombre',
            'last_name': 'NuevoApellido',
            'email': 'nuevo_email@test.com',
            'tipo_documento': 'CE',
            'numero_documento': '11223344'
        })
        self.assertEqual(response.status_code, 302)  # Redirects back to dashboard/panel
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NuevoNombre')
        self.assertEqual(self.user.last_name, 'NuevoApellido')
        self.assertEqual(self.user.email, 'nuevo_email@test.com')
        self.assertEqual(self.user.tipo_documento, 'CE')
        self.assertEqual(self.user.numero_documento, '11223344')

    def test_editar_perfil_invalid_data(self):
        """Verify validation errors are caught when submitting bad data."""
        self.client.login(email='perfil@test.com', password='password123')
        response = self.client.post(reverse('editar_perfil'), {
            'first_name': 'Nombre123',  # Contains numeric characters (invalid)
            'last_name': 'Apellido',
            'email': 'nuevo_email@test.com',
            'tipo_documento': 'CC',
            'numero_documento': 'documento123'  # Contains alphabetical characters (invalid)
        })
        self.assertEqual(response.status_code, 200)  # Renders form again with errors
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.first_name, 'Nombre123')
        form = response.context['form']
        self.assertIn('first_name', form.errors)
        self.assertIn('numero_documento', form.errors)


class PDFGenerationTestCase(TestCase):
    """
    Test suite for checking the generation, authorization, and formatting
    of downloadable PDF reports (turnos.pdf and usuarios.pdf).
    """

    def setUp(self):
        """
        Set up the testing database with necessary users and turnos
        for generating mock PDF reports.
        """
        self.company = Company.objects.create(name='Empresa PDF Integration', nit='900.222.222-9')
        # Create an administrative user (authorized)
        self.admin = Usuario.objects.create_user(
            username='admin_pdf',
            email='admin_pdf@test.com',
            password='password123',
            rol='admin',
            company=self.company
        )
        # Create a client user (unauthorized)
        self.cliente = Usuario.objects.create_user(
            username='cliente_pdf',
            email='cliente_pdf@test.com',
            password='password123',
            rol='cliente',
            tipo_documento='CC',
            numero_documento='11122233',
            company=self.company
        )
        # Create an employee user (unauthorized)
        self.empleado = Usuario.objects.create_user(
            username='empleado_pdf',
            email='empleado_pdf@test.com',
            password='password123',
            rol='empleado',
            company=self.company
        )
        # Create a couple of mock tickets
        Turno.objects.create(
            company=self.company,
            cliente=self.cliente,
            empleado=self.empleado,
            tipo_documento='CC',
            numero_documento='11122233',
            motivo='Consulta Médica',
            fecha=timezone.now().date(),
            hora='10:00',
            estado='Pendiente'
        )
        Turno.objects.create(
            company=self.company,
            cliente=self.cliente,
            empleado=self.empleado,
            tipo_documento='CC',
            numero_documento='11122233',
            motivo='Trámite Interno',
            fecha=timezone.now().date(),
            hora='11:00',
            estado='Atendido'
        )

    def test_turnos_pdf_requiere_autenticacion(self):
        """
        Verifica que el endpoint de turnos_pdf requiera inicio de sesión
        y redirija al login en caso de usuarios no autenticados.
        """
        response = self.client.get(reverse('turnos_pdf'))
        # Se espera una redirección a la pantalla de inicio de sesión
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_turnos_pdf_no_permite_cliente_o_empleado(self):
        """
        Verifica que clientes y empleados tengan el acceso denegado (HTTP 403)
        al intentar descargar el reporte PDF de turnos.
        """
        # Probar como cliente
        self.client.login(email='cliente_pdf@test.com', password='password123')
        response = self.client.get(reverse('turnos_pdf'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Probar como empleado
        self.client.login(email='empleado_pdf@test.com', password='password123')
        response = self.client.get(reverse('turnos_pdf'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

    def test_turnos_pdf_exito_admin_sin_filtros(self):
        """
        Verifica que un administrador pueda descargar el PDF completo sin filtros
        y reciba un stream binario de tipo application/pdf válido.
        """
        self.client.login(email='admin_pdf@test.com', password='password123')
        response = self.client.get(reverse('turnos_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="turnos.pdf"', response['Content-Disposition'])
        
        # Validar la firma estándar del encabezado del archivo PDF (%PDF)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_turnos_pdf_exito_admin_con_filtros(self):
        """
        Verifica que el administrador pueda descargar el PDF filtrado por estado
        con un resultado exitoso.
        """
        self.client.login(email='admin_pdf@test.com', password='password123')
        response = self.client.get(reverse('turnos_pdf') + '?estado=Atendido')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="turnos.pdf"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_usuarios_pdf_requiere_autenticacion_y_solo_admin(self):
        """
        Verifica el flujo de seguridad para el reporte PDF de usuarios:
        - Redirige si no está autenticado (HTTP 302).
        - Deniega acceso a clientes (HTTP 403).
        - Entrega el PDF de forma exitosa a administradores (HTTP 200).
        """
        # 1. Sin autenticación
        response = self.client.get(reverse('usuarios_pdf'))
        self.assertEqual(response.status_code, 302)

        # 2. Con rol cliente (No autorizado)
        self.client.login(email='cliente_pdf@test.com', password='password123')
        response = self.client.get(reverse('usuarios_pdf'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # 3. Con rol administrador (Autorizado)
        self.client.login(email='admin_pdf@test.com', password='password123')
        response = self.client.get(reverse('usuarios_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="usuarios.pdf"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
