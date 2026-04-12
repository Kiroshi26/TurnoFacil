from django.contrib.auth.backends import ModelBackend
from .models import Usuario


class EmailBackend(ModelBackend):
    """Permite autenticar con correo electrónico en vez de username."""

    def authenticate(self, request, email=None, password=None, **kwargs):
        try:
            user = Usuario.objects.get(email__iexact=email)
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except Usuario.DoesNotExist:
            return None
        except Usuario.MultipleObjectsReturned:
            # Si hay varios con el mismo email toma el primero activo
            user = Usuario.objects.filter(email__iexact=email, is_active=True).first()
            if user and user.check_password(password):
                return user
        return None