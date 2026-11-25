from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Catálogos"

    def ready(self):
        from django.contrib import admin

        admin.site.site_header = "SIS"
        admin.site.site_title = "SIS"
        admin.site.index_title = "Administración del sistema"
