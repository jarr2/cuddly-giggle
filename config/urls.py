from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from django.views.generic import RedirectView

from apps.usuarios.forms import AccesoForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "cuentas/entrar/",
        LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=AccesoForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("cuentas/salir/", LogoutView.as_view(), name="logout"),
    path("", RedirectView.as_view(pattern_name="tickets:lista", permanent=False)),
    path("tickets/", include("apps.tickets.urls")),
    path("", include("apps.usuarios.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
