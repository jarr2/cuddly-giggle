from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/contrasena/", views.CambiarContrasena.as_view(), name="contrasena"),
    path("usuarios/", views.ListaUsuarios.as_view(), name="lista"),
    path("usuarios/nuevo/", views.CrearUsuario.as_view(), name="nuevo"),
    path("usuarios/<int:pk>/editar/", views.EditarUsuario.as_view(), name="editar"),
    path("usuarios/<int:pk>/eliminar/", views.eliminar_usuario, name="eliminar"),
]
