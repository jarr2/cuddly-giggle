from django.contrib import admin

from .models import AdjuntoTicket, HistorialTicket, Ticket


class HistorialInline(admin.TabularInline):
    model = HistorialTicket
    extra = 0
    can_delete = False
    readonly_fields = ("fecha", "atencion_brindada", "estatus", "creado_por", "comentario")

    def has_add_permission(self, request, obj=None):
        return False


class AdjuntoInline(admin.TabularInline):
    model = AdjuntoTicket
    extra = 0
    can_delete = False
    readonly_fields = ("archivo", "tipo", "subido_por", "fecha")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("clave", "area", "estatus", "creado_por", "tecnico_asignado", "fecha_creacion")
    list_filter = ("estatus", "area")
    search_fields = ("clave", "descripcion", "creado_por__username", "creado_por__first_name")
    readonly_fields = (
        "clave",
        "estatus",
        "fecha_creacion",
        "fecha_finalizacion",
        "creado_por",
        "extension",
        "area",
        "descripcion",
        "tecnico_asignado",
    )
    inlines = [HistorialInline, AdjuntoInline]

    def has_add_permission(self, request):
        return False
