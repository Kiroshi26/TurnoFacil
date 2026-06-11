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
