from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import Area, CentroComputo
from apps.usuarios.models import Rol, Usuario

PASSWORD_DEMO = "Demo12345"

AREAS = (
    ("DTI", "SS", "Soporte y Sistemas"),
    ("DAF", "RM", "Recursos Materiales"),
    ("VIC", "PD", "Prensa y Difusión"),
)

USUARIOS = (
    ("general", "Ana", "Ruiz", Rol.GENERAL, "DTI", "101"),
    ("gestor", "Luis", "Mora", Rol.GESTOR, "VIC", "202"),
    ("tecnico.ss", "Carla", "Díaz", Rol.TECNICO, "DTI", "310"),
    ("tecnico.rm", "Jorge", "Paz", Rol.TECNICO, "DAF", "311"),
    ("tecnico.pd", "Nadia", "Solís", Rol.TECNICO, "VIC", "312"),
    ("admin.ss", "Elena", "Cruz", Rol.ADMIN_AREA, "DTI", "401"),
    ("admin.rm", "Mario", "Gil", Rol.ADMIN_AREA, "DAF", "402"),
    ("admin.pd", "Sofía", "León", Rol.ADMIN_AREA, "VIC", "403"),
    ("admin", "Admin", "Sistema", Rol.ADMIN_SISTEMA, None, "100"),
)


class Command(BaseCommand):
    help = "Crea las áreas DTI-SS, DAF-RM y VIC-PD, un centro de cómputo y usuarios de demostración."

    def handle(self, *args, **options):
        anio = timezone.localdate().year
        areas = {}
        for codigo, subcodigo, nombre in AREAS:
            area, _ = Area.objects.get_or_create(
                codigo=codigo,
                subcodigo=subcodigo,
                defaults={
                    "nombre": nombre,
                    "secuencia_anio": anio,
                    "secuencia_actual": 0,
                },
            )
            areas[codigo] = area
            self.stdout.write(f"Área {area}")

        CentroComputo.objects.get_or_create(
            clave="CC-01",
            defaults={
                "nombre": "Centro de cómputo principal",
                "area": areas["DTI"],
                "ubicacion": "Edificio de sistemas",
                "activo": True,
            },
        )
        self.stdout.write("Centro de cómputo CC-01")

        for username, nombre, apellido, rol, codigo_area, extension in USUARIOS:
            if Usuario.objects.filter(username=username).exists():
                self.stdout.write(f"Usuario {username} ya existe")
                continue
            usuario = Usuario(
                username=username,
                first_name=nombre,
                last_name=apellido,
                email=f"{username}@sis.local",
                rol=rol,
                area=areas.get(codigo_area) if codigo_area else None,
                extension=extension,
                is_staff=rol == Rol.ADMIN_SISTEMA,
                is_superuser=rol == Rol.ADMIN_SISTEMA,
            )
            usuario.set_password(PASSWORD_DEMO)
            usuario.save()
            self.stdout.write(f"Usuario {username} creado")

        self.stdout.write(self.style.SUCCESS(f"Contraseña de los usuarios nuevos: {PASSWORD_DEMO}"))
