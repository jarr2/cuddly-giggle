from django.contrib import admin

from .models import Area, CentroComputo


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "subcodigo", "nombre", "secuencia_anio", "secuencia_actual")
    search_fields = ("codigo", "subcodigo", "nombre")
    readonly_fields = ("secuencia_anio", "secuencia_actual")


@admin.register(CentroComputo)
class CentroComputoAdmin(admin.ModelAdmin):
    list_display = ("clave", "nombre", "area", "ubicacion", "activo")
    list_filter = ("activo", "area")
    search_fields = ("clave", "nombre", "ubicacion")
