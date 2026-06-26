from django.test import TestCase
from django.utils import timezone
from django.core import mail
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from core.models import Usuario, Turno, Company
from core.forms import TurnoForm, UsuarioForm

class TurnoTestCase(TestCase):
    def setUp(self):
        # Crear empresa de prueba
        self.company = Company.objects.create(
            name='Empresa Claro',
            nit='900.123.456-1',
            business_config={'slot_duration': 20, 'opening_time': '07:00', 'closing_time': '17:00'}
        )
        
        # Crear usuarios asociados a la empresa
        self.admin = Usuario.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='password123',
            rol='admin',
            company=self.company
        )
        self.empleado = Usuario.objects.create_user(
            username='empleado_user',
            email='empleado@test.com',
            password='password123',
            rol='empleado',
            company=self.company
        )
        self.cliente = Usuario.objects.create_user(
            username='cliente_user',
            email='cliente@test.com',
            password='password123',
            rol='cliente',
            tipo_documento='CC',
            numero_documento='12345678',
            company=self.company
        )
        
        # Crear un turno pendiente
        self.turno = Turno.objects.create(
            company=self.company,
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
        self.company = Company.objects.create(name='Empresa Movistar', nit='900.789.012-3')
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


class PDFGenerationTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Empresa Tigo', nit='900.456.789-2')
        
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
        # Create mock tickets
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
        response = self.client.get(reverse('turnos_pdf'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_turnos_pdf_no_permite_cliente_o_empleado(self):
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
        self.client.login(email='admin_pdf@test.com', password='password123')
        response = self.client.get(reverse('turnos_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="turnos.pdf"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_turnos_pdf_exito_admin_con_filtros(self):
        self.client.login(email='admin_pdf@test.com', password='password123')
        response = self.client.get(reverse('turnos_pdf') + '?estado=Atendido')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="turnos.pdf"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_usuarios_pdf_requiere_autenticacion_y_solo_admin(self):
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


class MultiTenantIsolationTestCase(TestCase):
    """
    Casos de prueba específicos para verificar el aislamiento estricto de datos (RLS)
    y las validaciones de negocio multi-inquilino.
    """
    def setUp(self):
        # Crear dos empresas independientes
        self.company1 = Company.objects.create(name='Empresa Claro', nit='900.111.111-1')
        self.company2 = Company.objects.create(name='Empresa Movistar', nit='900.222.222-2')

        # Admin de la Empresa Claro
        self.admin_claro = Usuario.objects.create_user(
            username='admin_claro', email='admin@claro.com', password='password123',
            rol='admin', company=self.company1
        )
        # Cliente de la Empresa Claro
        self.cliente_claro = Usuario.objects.create_user(
            username='cliente_claro', email='cliente@claro.com', password='password123',
            rol='cliente', company=self.company1
        )
        # Empleado de la Empresa Claro
        self.empleado_claro = Usuario.objects.create_user(
            username='empleado_claro', email='empleado@claro.com', password='password123',
            rol='empleado', company=self.company1
        )

        # Admin de la Empresa Movistar
        self.admin_movistar = Usuario.objects.create_user(
            username='admin_movistar', email='admin@movistar.com', password='password123',
            rol='admin', company=self.company2
        )
        # Cliente de la Empresa Movistar
        self.cliente_movistar = Usuario.objects.create_user(
            username='cliente_movistar', email='cliente@movistar.com', password='password123',
            rol='cliente', company=self.company2
        )
        # Empleado de la Empresa Movistar
        self.empleado_movistar = Usuario.objects.create_user(
            username='empleado_movistar', email='empleado@movistar.com', password='password123',
            rol='empleado', company=self.company2
        )

        # Crear turnos en ambas empresas
        self.turno_claro = Turno.objects.create(
            company=self.company1, cliente=self.cliente_claro, empleado=self.empleado_claro,
            tipo_documento='CC', numero_documento='123', motivo='Consulta Claro',
            fecha=timezone.now().date(), hora='08:00'
        )
        self.turno_movistar = Turno.objects.create(
            company=self.company2, cliente=self.cliente_movistar, empleado=self.empleado_movistar,
            tipo_documento='CC', numero_documento='456', motivo='Consulta Movistar',
            fecha=timezone.now().date(), hora='08:30'
        )

        # Superusuario global
        self.superuser = Usuario.objects.create_superuser(
            username='super_admin', email='super@global.com', password='password123'
        )

    def test_aislamiento_de_datos_lista_turnos(self):
        """
        Verifica que el admin de la Empresa Claro solo pueda ver sus propios turnos.
        """
        self.client.login(email='admin@claro.com', password='password123')
        response = self.client.get(reverse('turnos_lista'))
        self.assertEqual(response.status_code, 200)
        
        # Debe contener el turno de Claro pero no el de Movistar
        turnos = response.context['turnos']
        self.assertIn(self.turno_claro, turnos)
        self.assertNotIn(self.turno_movistar, turnos)

    def test_aislamiento_de_datos_editar_turno_ajeno(self):
        """
        Verifica que el admin de Claro no pueda editar ni ver el turno de Movistar (HTTP 404).
        """
        self.client.login(email='admin@claro.com', password='password123')
        url = reverse('turno_editar', kwargs={'pk': self.turno_movistar.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_usuario_sin_empresa_deniega_acceso(self):
        """
        Verifica que un usuario que no sea superusuario y no tenga empresa asignada sea rechazado.
        """
        usuario_sin_company = Usuario.objects.create_user(
            username='sin_empresa', email='sin@empresa.com', password='password123', rol='admin'
        )
        self.client.login(email='sin@empresa.com', password='password123')
        response = self.client.get(reverse('turnos_lista'))
        self.assertEqual(response.status_code, 403)  # PermissionDenied

    def test_superusuario_puede_ver_todo(self):
        """
        Verifica que el superusuario global (sin empresa) tenga acceso a todos los turnos.
        """
        self.client.login(email='super@global.com', password='password123')
        response = self.client.get(reverse('turnos_lista'))
        self.assertEqual(response.status_code, 200)
        
        turnos = response.context['turnos']
        self.assertEqual(len(turnos), 2)
        self.assertIn(self.turno_claro, turnos)
        self.assertIn(self.turno_movistar, turnos)

    def test_turno_form_previene_asignacion_cruzada(self):
        """
        Verifica que el TurnoForm impida asignar un empleado de Movistar a un turno de Claro.
        """
        form_data = {
            'company': self.company1.id,
            'cliente': self.cliente_claro.id,
            'empleado': self.empleado_movistar.id, # Empleado ajeno
            'tipo_documento': 'CC',
            'numero_documento': '123',
            'motivo': 'Intento cruzado',
            'fecha': timezone.now().date(),
            'hora': '10:00',
            'estado': 'Pendiente'
        }
        
        # Caso 1: Admin de Claro (falla a nivel de campo por queryset restringido)
        form = TurnoForm(data=form_data, user=self.admin_claro)
        self.assertFalse(form.is_valid())
        self.assertIn('empleado', form.errors)
        
        # Caso 2: Superusuario (falla a nivel de campo por queryset de empleados filtrado por la empresa elegida)
        form_super = TurnoForm(data=form_data, user=self.superuser)
        self.assertFalse(form_super.is_valid())
        self.assertIn('empleado', form_super.errors)

    def test_turno_form_excluye_empleado_para_clientes(self):
        """
        Verifica que el campo 'empleado' no esté disponible en el formulario
        para los usuarios con rol 'cliente'.
        """
        # Caso 1: Usuario Cliente
        form_cliente = TurnoForm(user=self.cliente_claro)
        self.assertNotIn('empleado', form_cliente.fields)

        # Caso 2: Usuario Admin (debe tener el campo disponible)
        form_admin = TurnoForm(user=self.admin_claro)
        self.assertIn('empleado', form_admin.fields)

        # Caso 3: Superusuario (debe tener el campo disponible)
        form_super = TurnoForm(user=self.superuser)
        self.assertIn('empleado', form_super.fields)

    def test_usuario_form_opciones_rol_y_company(self):
        """
        Verifica que el UsuarioForm configure correctamente los roles y excluya/incluya
        el campo de empresa (company) según el usuario solicitante (Admin de inquilino vs Superusuario).
        """
        # Caso 1: Admin de Empresa Claro (no debe ver la opción de cambiar empresa)
        form_admin = UsuarioForm(user=self.admin_claro)
        self.assertNotIn('company', form_admin.fields)
        self.assertEqual(
            form_admin.fields['rol'].choices,
            [('admin', 'Administrador de Empresa'), ('empleado', 'Empleado')]
        )

        # Caso 2: Superusuario (debe ver la opción de asignar empresa)
        form_super = UsuarioForm(user=self.superuser)
        self.assertIn('company', form_super.fields)

    def test_usuario_creacion_y_edicion_por_admin(self):
        """
        Verifica que un administrador de empresa pueda crear y editar un nuevo usuario
        asociándole un rol específico (empleado o admin) y que éste pertenezca a la misma empresa.
        """
        self.client.login(email='admin@claro.com', password='password123')
        
        # 1. Crear nuevo empleado
        crear_url = reverse('usuario_crear')
        post_data = {
            'first_name': 'Nuevo',
            'last_name': 'Empleado',
            'username': 'nuevo_emp',
            'email': 'nuevo_emp@claro.com',
            'rol': 'empleado',
            'password': 'PasswordSecure123!'
        }
        response = self.client.post(crear_url, post_data)
        self.assertEqual(response.status_code, 302)  # Redirección exitosa
        
        # Verificar que el usuario fue creado con la empresa del admin
        nuevo_usuario = Usuario.objects.get(username='nuevo_emp')
        self.assertEqual(nuevo_usuario.rol, 'empleado')
        self.assertEqual(nuevo_usuario.company, self.company1)
        self.assertTrue(nuevo_usuario.check_password('PasswordSecure123!'))

        # 2. Editar el usuario para cambiarle el rol a admin
        editar_url = reverse('usuario_editar', kwargs={'pk': nuevo_usuario.pk})
        update_data = {
            'first_name': 'NuevoEditado',
            'last_name': 'Empleado',
            'username': 'nuevo_emp',
            'email': 'nuevo_emp@claro.com',
            'rol': 'admin',
            'password': ''  # Dejar en blanco para no alterar contraseña
        }
        response = self.client.post(editar_url, update_data)
        self.assertEqual(response.status_code, 302)

        # Verificar actualización del rol
        nuevo_usuario.refresh_from_db()
        self.assertEqual(nuevo_usuario.first_name, 'NuevoEditado')
        self.assertEqual(nuevo_usuario.rol, 'admin')
        self.assertTrue(nuevo_usuario.check_password('PasswordSecure123!'))

    def test_generacion_numero_turno_por_empresa(self):
        """
        Verifica que los códigos de turnos generados dependan de la empresa y se incrementen correlativamente.
        """
        # Los turnos creados en setUp ya deben tener los primeros códigos de Claro y Movistar
        self.assertEqual(self.turno_claro.numero_turno, 'C-100')
        self.assertEqual(self.turno_movistar.numero_turno, 'M-200')

        # Crear nuevos turnos (deberían dar C-101 y M-201 respectivamente)
        turno1_claro = Turno.objects.create(
            company=self.company1, cliente=self.cliente_claro, empleado=self.empleado_claro,
            tipo_documento='CC', numero_documento='123', motivo='Consulta 1',
            fecha=timezone.now().date(), hora='08:00'
        )
        self.assertEqual(turno1_claro.numero_turno, 'C-101')

        turno1_movistar = Turno.objects.create(
            company=self.company2, cliente=self.cliente_movistar, empleado=self.empleado_movistar,
            tipo_documento='CC', numero_documento='456', motivo='Consulta 3',
            fecha=timezone.now().date(), hora='08:00'
        )
        self.assertEqual(turno1_movistar.numero_turno, 'M-201')

        # Crear empresa Tigo (debería dar T-300, etc.)
        company_tigo = Company.objects.create(name='Empresa Tigo', nit='900.333.333-3')
        turno1_tigo = Turno.objects.create(
            company=company_tigo, cliente=self.cliente_movistar, empleado=self.empleado_movistar,
            tipo_documento='CC', numero_documento='456', motivo='Consulta 4',
            fecha=timezone.now().date(), hora='08:00'
        )
        self.assertEqual(turno1_tigo.numero_turno, 'T-300')
