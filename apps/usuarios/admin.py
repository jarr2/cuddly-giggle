from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "nombre", "email", "rol", "area", "extension", "is_active")
    list_filter = ("rol", "area", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email", "extension")
    fieldsets = UserAdmin.fieldsets + (
        ("SIS", {"fields": ("rol", "area", "extension", "telefono")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("SIS", {"fields": ("first_name", "last_name", "rol", "area", "extension", "telefono")}),
    )
    ordering = ("username",)
