from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Rol


def usuario_tiene_rol(usuario, roles) -> bool:
    return usuario.is_authenticated and usuario.rol in roles


def rol_requerido(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def envuelta(request, *args, **kwargs):
            if not usuario_tiene_rol(request.user, roles):
                raise PermissionDenied("Tu rol no puede entrar a esta sección.")
            return view(request, *args, **kwargs)

        return envuelta

    return decorator


class RolRequeridoMixin(LoginRequiredMixin):
    roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.rol not in self.roles:
            raise PermissionDenied("Tu rol no puede entrar a esta sección.")
        return super().dispatch(request, *args, **kwargs)


ROLES_OPERACION = (
    Rol.GENERAL,
    Rol.GESTOR,
    Rol.TECNICO,
    Rol.ADMIN_AREA,
    Rol.ADMIN_SISTEMA,
)
