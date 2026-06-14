from django.test import TestCase
from django.utils import timezone
from django.core import mail
from django.urls import reverse
from core.models import Usuario, Turno


class TurnoTestCase(TestCase):
    def setUp(self):
        # Crear usuarios para las pruebas
        self.admin = Usuario.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='password123',
            rol='admin'
        )
        self.empleado = Usuario.objects.create_user(
            username='empleado_user',
            email='empleado@test.com',
            password='password123',
            rol='empleado'
        )
        self.cliente = Usuario.objects.create_user(
            username='cliente_user',
            email='cliente@test.com',
            password='password123',
            rol='cliente',
            tipo_documento='CC',
            numero_documento='12345678'
        )
        # Crear un turno pendiente
        self.turno = Turno.objects.create(
            cliente=self.cliente,
            empleado=self.empleado,
            tipo_documento='CC',
            numero_documento='12345678',
            motivo='Trámite Administrativo',
            fecha=timezone.now().date(),
            hora='09:00',
            estado='Pendiente'
        )

    def test_llamar_turno_envia_correo(self):
        # Autenticar como el empleado asignado al turno
        self.client.login(email='empleado@test.com', password='password123')

        # Realizar la petición POST para llamar al turno
        url = reverse('llamar_turno', kwargs={'pk': self.turno.pk})
        response = self.client.post(url)

        # Verificar respuesta exitosa
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        # Verificar actualización del turno en la base de datos
        self.turno.refresh_from_db()
        self.assertTrue(self.turno.llamado)
        self.assertIsNotNone(self.turno.llamado_en)

        # Verificar que se envió exactamente un correo electrónico
        self.assertEqual(len(mail.outbox), 1)
        email_enviado = mail.outbox[0]
        
        # Verificar destinatario, asunto y cuerpo del mensaje
        self.assertEqual(email_enviado.to, [self.cliente.email])
        self.assertIn(self.turno.numero_turno, email_enviado.subject)
        self.assertIn(self.empleado.username, email_enviado.body)
        self.assertIn('Trámite Administrativo', email_enviado.body)


class AuthAndProfileTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            username='perfil_user',
            email='perfil@test.com',
            password='password123',
            rol='cliente',
            tipo_documento='CC',
            numero_documento='98765432'
        )

    def test_registro_page_loads(self):
        response = self.client.get(reverse('registro'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/registro.html')

    def test_password_reset_request_sends_email(self):
        response = self.client.post(reverse('password_reset'), {'email': 'perfil@test.com'})
        self.assertEqual(response.status_code, 302)  # Redirects to done
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['perfil@test.com'])
        self.assertIn('password-reset-confirm', email.body)

    def test_editar_perfil_requires_login(self):
        response = self.client.get(reverse('editar_perfil'))
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_editar_perfil_update(self):
        self.client.login(email='perfil@test.com', password='password123')
        response = self.client.post(reverse('editar_perfil'), {
            'first_name': 'NuevoNombre',
            'last_name': 'NuevoApellido',
            'email': 'nuevo_email@test.com',
            'tipo_documento': 'CE',
            'numero_documento': '11223344'
        })
        self.assertEqual(response.status_code, 302)  # Redirects to panel
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NuevoNombre')
        self.assertEqual(self.user.last_name, 'NuevoApellido')
        self.assertEqual(self.user.email, 'nuevo_email@test.com')
        self.assertEqual(self.user.tipo_documento, 'CE')
        self.assertEqual(self.user.numero_documento, '11223344')

    def test_editar_perfil_invalid_data(self):
        self.client.login(email='perfil@test.com', password='password123')
        response = self.client.post(reverse('editar_perfil'), {
            'first_name': 'Nombre123',
            'last_name': 'Apellido',
            'email': 'nuevo_email@test.com',
            'tipo_documento': 'CC',
            'numero_documento': 'documento123'
        })
        self.assertEqual(response.status_code, 200)  # Form returns page with errors
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.first_name, 'Nombre123')
        form = response.context['form']
        self.assertIn('first_name', form.errors)
        self.assertIn('numero_documento', form.errors)


