from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import Area


class Rol(models.TextChoices):
    GENERAL = "general", "Usuario general"
    GESTOR = "gestor", "Usuario general y gestor de eventos"
    TECNICO = "tecnico", "Técnico"
    ADMIN_AREA = "admin_area", "Administrador de área"
    ADMIN_SISTEMA = "admin_sistema", "Administrador de sistema"


class Usuario(AbstractUser):
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.GENERAL,
        verbose_name="Rol",
    )
    area = models.ForeignKey(
        Area,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="usuarios",
        verbose_name="Área",
    )
    extension = models.CharField(max_length=20, blank=True, verbose_name="Extensión")
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        swappable = "AUTH_USER_MODEL"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rol__in=Rol.values),
                name="usuario_rol_valido",
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.username})"

    def clean(self):
        super().clean()
        if self.rol in {Rol.TECNICO, Rol.ADMIN_AREA} and not self.area_id:
            raise ValidationError({"area": "Este rol requiere un área."})

    @property
    def nombre(self):
        completo = self.get_full_name().strip()
        return completo or self.username
