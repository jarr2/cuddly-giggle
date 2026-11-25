from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/asignar/", views.asignar, name="asignar"),
    path("<int:pk>/atender/", views.atender, name="atender"),
    path("<int:pk>/visto-bueno/", views.visto_bueno, name="visto_bueno"),
    path("<int:pk>/adjuntos/", views.adjuntos, name="adjuntos"),
]
