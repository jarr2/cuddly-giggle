from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from .forms import ContrasenaForm, PerfilForm, UsuarioForm
from .models import Rol, Usuario
from .permissions import RolRequeridoMixin, rol_requerido


class ListaUsuarios(RolRequeridoMixin, ListView):
    roles = (Rol.ADMIN_SISTEMA,)
    model = Usuario
    template_name = "usuarios/lista.html"
    context_object_name = "usuarios"
    queryset = Usuario.objects.select_related("area").order_by("username")


class CrearUsuario(RolRequeridoMixin, CreateView):
    roles = (Rol.ADMIN_SISTEMA,)
    model = Usuario
    form_class = UsuarioForm
    template_name = "usuarios/formulario.html"
    success_url = reverse_lazy("usuarios:lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = "Nuevo usuario"
        return contexto

    def form_valid(self, form):
        messages.success(self.request, "Usuario creado.")
        return super().form_valid(form)


class EditarUsuario(RolRequeridoMixin, UpdateView):
    roles = (Rol.ADMIN_SISTEMA,)
    model = Usuario
    form_class = UsuarioForm
    template_name = "usuarios/formulario.html"
    success_url = reverse_lazy("usuarios:lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = f"Editar {self.object.username}"
        return contexto

    def form_valid(self, form):
        messages.success(self.request, "Usuario actualizado.")
        return super().form_valid(form)


@rol_requerido(Rol.ADMIN_SISTEMA)
@require_POST
def eliminar_usuario(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propio usuario.")
        return redirect("usuarios:lista")
    try:
        usuario.delete()
    except ProtectedError:
        messages.error(
            request,
            "No se puede eliminar: tiene reportes u otro historial asociado.",
        )
    else:
        messages.success(request, "Usuario eliminado.")
    return redirect("usuarios:lista")


@login_required
def perfil(request):
    form = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil actualizado.")
        return redirect("usuarios:perfil")
    return render(request, "usuarios/perfil.html", {"form": form})


class CambiarContrasena(PasswordChangeView):
    form_class = ContrasenaForm
    template_name = "usuarios/contrasena.html"
    success_url = reverse_lazy("usuarios:perfil")

    def form_valid(self, form):
        messages.success(self.request, "Contraseña actualizada.")
        return super().form_valid(form)
