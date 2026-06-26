from functools import wraps
from django.shortcuts import redirect, render
from django.contrib import messages


def login_requerido(view_func):
    """Exige que el usuario esté autenticado, redirige a login propio."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def rol_requerido(*roles):
    """Decorador que exige que el usuario tenga uno de los roles indicados."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            # Superusuario bypasses role constraints
            if request.user.is_superuser or request.user.rol in roles:
                return view_func(request, *args, **kwargs)
            return render(request, '403.html', status=403)
        return wrapper
    return decorator


def solo_admin(view_func):
    return rol_requerido('admin')(view_func)


def solo_empleado(view_func):
    return rol_requerido('empleado')(view_func)


def solo_cliente(view_func):
    return rol_requerido('cliente')(view_func)


def admin_o_empleado(view_func):
    return rol_requerido('admin', 'empleado')(view_func)