from pathlib import Path

from django.db import models
from django.utils import timezone

from apps.core.models import Area
from apps.usuarios.models import Usuario


class EstatusTicket(models.TextChoices):
    ABIERTO = "abierto", "Abierto"
    ASIGNADO = "asignado", "Asignado"
    PENDIENTE = "pendiente", "Pendiente"
    FINALIZADO = "finalizado", "Finalizado"
    CANCELADO = "cancelado", "Cancelado"
    CONCLUIDO = "concluido", "Concluido"
    VISTO_BUENO = "visto_bueno", "Visto bueno"


class TipoAdjunto(models.TextChoices):
    IMAGEN = "imagen", "Imagen"
    PDF = "pdf", "PDF"
    EXCEL = "excel", "Excel"
    WORD = "word", "Word"


def ruta_adjunto(instance, filename):
    nombre = Path(filename).name
    return f"tickets/{timezone.now():%Y/%m}/{nombre}"


class Ticket(models.Model):
    clave = models.CharField(max_length=48, unique=True, editable=False, verbose_name="Clave")
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="tickets_creados",
        verbose_name="Solicitante",
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="tickets",
        verbose_name="Área",
    )
    extension = models.CharField(max_length=20, verbose_name="Extensión")
    descripcion = models.TextField(verbose_name="Descripción")
    tecnico_asignado = models.ForeignKey(
        Usuario,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tickets_asignados",
        verbose_name="Técnico asignado",
    )
    estatus = models.CharField(
        max_length=20,
        choices=EstatusTicket.choices,
        default=EstatusTicket.ABIERTO,
        db_index=True,
        verbose_name="Estatus",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de emisión")
    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Fecha de finalización",
    )

    class Meta:
        verbose_name = "reporte"
        verbose_name_plural = "reportes"
        ordering = ["-fecha_creacion", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estatus__in=EstatusTicket.values),
                name="ticket_estatus_valido",
            )
        ]

    def __str__(self):
        return self.clave


class HistorialTicket(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="historial",
        verbose_name="Reporte",
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    atencion_brindada = models.TextField(verbose_name="Atención brindada")
    estatus = models.CharField(
        max_length=20,
        choices=EstatusTicket.choices,
        verbose_name="Estatus",
    )
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="historial_registrado",
        verbose_name="Registró",
    )
    comentario = models.TextField(blank=True, verbose_name="Comentario")

    class Meta:
        verbose_name = "historial"
        verbose_name_plural = "historiales"
        ordering = ["fecha", "id"]
        indexes = [models.Index(fields=["ticket", "fecha"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estatus__in=EstatusTicket.values),
                name="historial_estatus_valido",
            )
        ]

    def __str__(self):
        return f"{self.ticket.clave} · {self.get_estatus_display()}"


class AdjuntoTicket(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="adjuntos",
        verbose_name="Reporte",
    )
    archivo = models.FileField(upload_to=ruta_adjunto, verbose_name="Archivo")
    tipo = models.CharField(max_length=20, choices=TipoAdjunto.choices, verbose_name="Tipo")
    subido_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="adjuntos_subidos",
        verbose_name="Subido por",
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "adjunto"
        verbose_name_plural = "adjuntos"
        ordering = ["fecha", "id"]

    def __str__(self):
        return self.nombre_archivo

    @property
    def nombre_archivo(self):
        return Path(self.archivo.name).name
