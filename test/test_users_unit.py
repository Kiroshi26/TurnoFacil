from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Usuario
from core.forms import PerfilForm, validar_solo_letras, validar_solo_numeros


class UserValidatorsTestCase(TestCase):
    """
    Unit tests for custom field validators:
    - validar_solo_letras (letters only, accents, ñ, spaces, hyphens)
    - validar_solo_numeros (digits only)
    """

    def test_validar_solo_letras_exito(self):
        """Verifica que strings con solo letras y caracteres permitidos pasen la validación."""
        valid_inputs = ["Juan", "Pérez", "María del Carmen", "Muñoz", "Smith-Jones"]
        for val in valid_inputs:
            try:
                validar_solo_letras(val)
            except ValidationError:
                self.fail(f"validar_solo_letras falló con una entrada válida: '{val}'")

    def test_validar_solo_letras_falla(self):
        """Verifica que se lance ValidationError cuando hay números o símbolos prohibidos."""
        invalid_inputs = ["Juan123", "Juan!", "Pér@z", "María_del_Carmen", "#Muñoz"]
        for val in invalid_inputs:
            with self.assertRaises(ValidationError):
                validar_solo_letras(val)

    def test_validar_solo_numeros_exito(self):
        """Verifica que strings que contienen únicamente dígitos pasen la validación."""
        valid_inputs = ["1013105858", "123456", "0987654321"]
        for val in valid_inputs:
            try:
                validar_solo_numeros(val)
            except ValidationError:
                self.fail(f"validar_solo_numeros falló con una entrada válida: '{val}'")

    def test_validar_solo_numeros_falla(self):
        """Verifica que se lance ValidationError cuando la entrada tiene letras o símbolos."""
        invalid_inputs = ["101310585a", "123-456", "12.345", " ", ""]
        for val in invalid_inputs:
            with self.assertRaises(ValidationError):
                validar_solo_numeros(val)


class UsuarioModelTestCase(TestCase):
    """
    Unit tests for the custom Usuario model methods and attributes.
    """

    def test_usuario_roles(self):
        """Verifica que los métodos de verificación de rol funcionen adecuadamente."""
        admin = Usuario(username='adm', rol='admin')
        self.assertTrue(admin.is_admin())
        self.assertFalse(admin.is_empleado())
        self.assertFalse(admin.is_cliente())

        empleado = Usuario(username='emp', rol='empleado')
        self.assertFalse(empleado.is_admin())
        self.assertTrue(empleado.is_empleado())
        self.assertFalse(empleado.is_cliente())

        cliente = Usuario(username='cli', rol='cliente')
        self.assertFalse(cliente.is_admin())
        self.assertFalse(cliente.is_empleado())
        self.assertTrue(cliente.is_cliente())

    def test_usuario_str_method(self):
        """Verifica la representación en string de un usuario (Nombre completo o username)."""
        # Caso 1: Usuario con Nombre y Apellido
        user_with_name = Usuario(username='juan_perez', first_name='Juan', last_name='Pérez')
        self.assertEqual(str(user_with_name), 'Juan Pérez')

        # Caso 2: Usuario sin nombre completo (retorna username)
        user_no_name = Usuario(username='juan_perez')
        self.assertEqual(str(user_no_name), 'juan_perez')


class PerfilFormTestCase(TestCase):
    """
    Unit tests for profile form validation logic (PerfilForm).
    """

    def test_perfil_form_valido(self):
        """Verifica que el formulario sea válido si se proporcionan datos correctos."""
        datos = {
            'first_name': 'Carlos',
            'last_name': 'Segovia',
            'email': 'carlos@test.com',
            'tipo_documento': 'CC',
            'numero_documento': '10992348'
        }
        form = PerfilForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_perfil_form_invalido_nombre(self):
        """Verifica que el formulario falle si el nombre contiene números."""
        datos = {
            'first_name': 'Carlos123',  # Nombre inválido
            'last_name': 'Segovia',
            'email': 'carlos@test.com',
            'tipo_documento': 'CC',
            'numero_documento': '10992348'
        }
        form = PerfilForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    def test_perfil_form_invalido_documento(self):
        """Verifica que el formulario falle si el número de documento contiene letras."""
        datos = {
            'first_name': 'Carlos',
            'last_name': 'Segovia',
            'email': 'carlos@test.com',
            'tipo_documento': 'CC',
            'numero_documento': '10992348abc'  # Documento inválido
        }
        form = PerfilForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn('numero_documento', form.errors)
