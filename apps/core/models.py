from django.core.exceptions import ValidationError
from django.db import models


class Area(models.Model):
    codigo = models.CharField(max_length=10, verbose_name="Código")
    subcodigo = models.CharField(max_length=10, verbose_name="Subcódigo")
    nombre = models.CharField(max_length=120, verbose_name="Nombre")
    secuencia_anio = models.PositiveIntegerField(default=0, verbose_name="Año de la secuencia")
    secuencia_actual = models.PositiveIntegerField(default=0, verbose_name="Secuencia actual")

    class Meta:
        verbose_name = "área"
        verbose_name_plural = "áreas"
        ordering = ["codigo", "subcodigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo", "subcodigo"],
                name="uniq_area_codigo_subcodigo",
            )
        ]

    def __str__(self):
        return f"{self.codigo}-{self.subcodigo} · {self.nombre}"

    def clean(self):
        super().clean()
        self.codigo = (self.codigo or "").strip().upper()
        self.subcodigo = (self.subcodigo or "").strip().upper()
        if not self.codigo.isalnum() or not self.subcodigo.isalnum():
            raise ValidationError("El código y el subcódigo solo usan letras y números.")

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        self.subcodigo = (self.subcodigo or "").strip().upper()
        super().save(*args, **kwargs)


class CentroComputo(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    clave = models.CharField(max_length=32, unique=True, verbose_name="Clave")
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="centros",
        verbose_name="Área",
    )
    ubicacion = models.CharField(max_length=200, blank=True, verbose_name="Ubicación")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "centro de cómputo"
        verbose_name_plural = "centros de cómputo"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
