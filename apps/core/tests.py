from django.core.management import call_command
from django.test import TestCase

from apps.core.models import Area, CentroComputo
from apps.usuarios.models import Usuario


class SeedTests(TestCase):
    def test_seed_es_idempotente(self):
        call_command("seed_areas")
        call_command("seed_areas")
        self.assertEqual(Area.objects.count(), 3)
        self.assertTrue(Area.objects.filter(codigo="DTI", subcodigo="SS").exists())
        self.assertTrue(Area.objects.filter(codigo="DAF", subcodigo="RM").exists())
        self.assertTrue(Area.objects.filter(codigo="VIC", subcodigo="PD").exists())
        self.assertTrue(CentroComputo.objects.filter(clave="CC-01").exists())
        self.assertEqual(Usuario.objects.filter(username="general").count(), 1)
        self.assertTrue(self.client.login(username="admin", password="Demo12345"))
