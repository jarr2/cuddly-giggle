from django.test import TestCase
from django.urls import reverse

from apps.core.models import Area
from apps.tickets.services import crear_ticket
from apps.usuarios.models import Rol, Usuario

PASSWORD = "Segura.2026.sis"


class UsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dti = Area.objects.create(
            codigo="DTI",
            subcodigo="SS",
            nombre="Soporte y Sistemas",
            secuencia_anio=2026,
            secuencia_actual=0,
        )
        cls.admin = Usuario.objects.create_user(
            "admin",
            password=PASSWORD,
            rol=Rol.ADMIN_SISTEMA,
            first_name="Admin",
            last_name="Sistema",
            extension="100",
        )
        cls.general = Usuario.objects.create_user(
            "general",
            password=PASSWORD,
            rol=Rol.GENERAL,
            area=cls.dti,
            first_name="Ana",
            last_name="Ruiz",
            extension="101",
        )

    def test_solo_el_admin_de_sistema_gestiona_usuarios(self):
        self.client.force_login(self.general)
        self.assertEqual(self.client.get(reverse("usuarios:lista")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("usuarios:lista")).status_code, 200)
        respuesta = self.client.post(
            reverse("usuarios:nuevo"),
            {
                "username": "tec.nuevo",
                "first_name": "Nora",
                "last_name": "Gil",
                "email": "nora@sis.local",
                "rol": Rol.TECNICO,
                "area": self.dti.pk,
                "extension": "515",
                "telefono": "",
                "password": PASSWORD,
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        creado = Usuario.objects.get(username="tec.nuevo")
        self.assertEqual(creado.rol, Rol.TECNICO)
        self.assertEqual(creado.area, self.dti)

    def test_tecnico_sin_area_no_se_crea(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("usuarios:nuevo"),
            {
                "username": "tec.sin",
                "first_name": "Sin",
                "last_name": "Area",
                "email": "",
                "rol": Rol.TECNICO,
                "area": "",
                "extension": "1",
                "telefono": "",
                "password": PASSWORD,
                "is_active": "on",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username="tec.sin").exists())

    def test_no_elimina_su_propia_cuenta_ni_quien_tiene_reportes(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("usuarios:eliminar", args=[self.admin.pk]))
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())
        crear_ticket(
            creador=self.general,
            area=self.dti,
            extension="101",
            descripcion="Reporte que impide borrar al solicitante.",
        )
        self.client.post(reverse("usuarios:eliminar", args=[self.general.pk]))
        self.assertTrue(Usuario.objects.filter(pk=self.general.pk).exists())
        suelto = Usuario.objects.create_user(
            "temporal",
            password=PASSWORD,
            rol=Rol.GENERAL,
            first_name="Tempo",
            last_name="Ral",
        )
        self.client.post(reverse("usuarios:eliminar", args=[suelto.pk]))
        self.assertFalse(Usuario.objects.filter(pk=suelto.pk).exists())
