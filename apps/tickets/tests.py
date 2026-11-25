import threading
from datetime import timedelta
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.core.models import Area
from apps.tickets.models import AdjuntoTicket, EstatusTicket, HistorialTicket, Ticket
from apps.tickets.services import (
    ErrorTicket,
    TransicionInvalida,
    asignar_ticket,
    atender_ticket,
    confirmar_visto_bueno,
    concluir_vencidos,
    crear_ticket,
    generar_clave,
)
from apps.tickets.states import puede_transicionar
from apps.tickets.validators import MAX_BYTES, validar_adjunto
from apps.usuarios.models import Rol, Usuario

PASSWORD = "Segura.2026.sis"


def _png(nombre="foto.png"):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), (18, 92, 64)).save(buffer, format="PNG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


def _pdf(nombre="nota.pdf"):
    return SimpleUploadedFile(
        nombre,
        b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF",
        content_type="application/pdf",
    )


class BaseReportes(TestCase):
    @classmethod
    def setUpTestData(cls):
        anio = timezone.localdate().year
        cls.dti = Area.objects.create(
            codigo="DTI",
            subcodigo="SS",
            nombre="Soporte y Sistemas",
            secuencia_anio=anio,
            secuencia_actual=0,
        )
        cls.daf = Area.objects.create(
            codigo="DAF",
            subcodigo="RM",
            nombre="Recursos Materiales",
            secuencia_anio=anio,
            secuencia_actual=0,
        )
        cls.general = Usuario.objects.create_user(
            "general",
            password=PASSWORD,
            rol=Rol.GENERAL,
            area=cls.dti,
            extension="101",
            first_name="Ana",
            last_name="Ruiz",
        )
        cls.tecnico_dti = Usuario.objects.create_user(
            "tecnico.ss",
            password=PASSWORD,
            rol=Rol.TECNICO,
            area=cls.dti,
            extension="310",
            first_name="Carla",
            last_name="Díaz",
        )
        cls.tecnico_daf = Usuario.objects.create_user(
            "tecnico.rm",
            password=PASSWORD,
            rol=Rol.TECNICO,
            area=cls.daf,
            extension="311",
            first_name="Jorge",
            last_name="Paz",
        )
        cls.admin_dti = Usuario.objects.create_user(
            "admin.ss",
            password=PASSWORD,
            rol=Rol.ADMIN_AREA,
            area=cls.dti,
            extension="401",
            first_name="Elena",
            last_name="Cruz",
        )
        cls.admin_daf = Usuario.objects.create_user(
            "admin.rm",
            password=PASSWORD,
            rol=Rol.ADMIN_AREA,
            area=cls.daf,
            extension="402",
            first_name="Mario",
            last_name="Gil",
        )
        cls.admin_sistema = Usuario.objects.create_user(
            "admin",
            password=PASSWORD,
            rol=Rol.ADMIN_SISTEMA,
            extension="100",
            first_name="Admin",
            last_name="Sistema",
        )

    def _crear(self, creador=None, area=None, descripcion="La impresora del laboratorio no enciende."):
        return crear_ticket(
            creador=creador or self.general,
            area=area or self.dti,
            extension="101",
            descripcion=descripcion,
        )


class ClaveTests(BaseReportes):
    def test_formato_y_secuencia_por_area(self):
        anio = timezone.localdate().year
        primera = generar_clave(self.dti)
        segunda = generar_clave(self.dti)
        otra_area = generar_clave(self.daf)
        self.assertRegex(primera, rf"^SIS-DTI-SS-{anio}-R-\d{{9}}$")
        self.assertTrue(primera.endswith("000000001"))
        self.assertTrue(segunda.endswith("000000002"))
        self.assertTrue(otra_area.endswith("000000001"))
        self.assertNotEqual(primera, segunda)

    def test_la_secuencia_reinicia_al_cambiar_el_anio(self):
        anio = timezone.localdate().year
        self.dti.secuencia_anio = anio - 1
        self.dti.secuencia_actual = 40
        self.dti.save(update_fields=["secuencia_anio", "secuencia_actual"])
        clave = generar_clave(self.dti)
        self.assertIn(f"-{anio}-R-000000001", clave)
        self.dti.refresh_from_db()
        self.assertEqual(self.dti.secuencia_actual, 1)
        self.assertEqual(self.dti.secuencia_anio, anio)

    def test_crear_reporte_guarda_clave_e_historial_inicial(self):
        ticket = self._crear()
        self.assertTrue(ticket.clave.startswith("SIS-DTI-SS-"))
        entrada = ticket.historial.get()
        self.assertEqual(entrada.atencion_brindada, "Has generado el reporte")
        self.assertEqual(entrada.estatus, EstatusTicket.ABIERTO)
        self.assertEqual(entrada.creado_por, self.general)


class TransicionTests(BaseReportes):
    def test_mapa_de_transiciones(self):
        self.assertTrue(puede_transicionar(EstatusTicket.ABIERTO, EstatusTicket.ASIGNADO))
        self.assertFalse(puede_transicionar(EstatusTicket.ABIERTO, EstatusTicket.FINALIZADO))
        self.assertTrue(puede_transicionar(EstatusTicket.ASIGNADO, EstatusTicket.PENDIENTE))
        self.assertTrue(puede_transicionar(EstatusTicket.ASIGNADO, EstatusTicket.CANCELADO))
        self.assertTrue(puede_transicionar(EstatusTicket.PENDIENTE, EstatusTicket.FINALIZADO))
        self.assertTrue(puede_transicionar(EstatusTicket.FINALIZADO, EstatusTicket.VISTO_BUENO))
        self.assertTrue(puede_transicionar(EstatusTicket.FINALIZADO, EstatusTicket.CONCLUIDO))
        self.assertTrue(puede_transicionar(EstatusTicket.VISTO_BUENO, EstatusTicket.CONCLUIDO))
        self.assertFalse(puede_transicionar(EstatusTicket.CANCELADO, EstatusTicket.ABIERTO))

    def test_no_se_puede_finalizar_un_reporte_abierto(self):
        ticket = self._crear()
        ticket.tecnico_asignado = self.tecnico_dti
        ticket.save(update_fields=["tecnico_asignado"])
        with self.assertRaises(TransicionInvalida):
            atender_ticket(ticket, self.tecnico_dti, "Revisé el equipo", EstatusTicket.FINALIZADO, "Falta refacción")

    def test_asignacion_solo_del_admin_de_la_misma_area(self):
        ticket = self._crear()
        with self.assertRaises(ErrorTicket):
            asignar_ticket(ticket, self.admin_daf, self.tecnico_daf)
        with self.assertRaises(ErrorTicket):
            asignar_ticket(ticket, self.admin_dti, self.tecnico_daf)
        asignado = asignar_ticket(ticket, self.admin_dti, self.tecnico_dti)
        self.assertEqual(asignado.estatus, EstatusTicket.ASIGNADO)
        self.assertEqual(asignado.tecnico_asignado, self.tecnico_dti)
        entrada = asignado.historial.order_by("id").last()
        self.assertEqual(entrada.atencion_brindada, "Se te ha sido asignado el tecnico: Carla Díaz")
        self.assertEqual(entrada.estatus, EstatusTicket.ASIGNADO)

    def test_tecnico_atiende_y_puede_ser_de_otra_area(self):
        ticket = self._crear(area=self.daf)
        ticket.estatus = EstatusTicket.ASIGNADO
        ticket.tecnico_asignado = self.tecnico_dti
        ticket.save(update_fields=["estatus", "tecnico_asignado"])
        atendido = atender_ticket(
            ticket,
            self.tecnico_dti,
            "Se cambió el fusible del centro de carga.",
            EstatusTicket.FINALIZADO,
            "La falla era eléctrica, no de redes.",
        )
        self.assertEqual(atendido.estatus, EstatusTicket.FINALIZADO)
        self.assertIsNotNone(atendido.fecha_finalizacion)
        entrada = atendido.historial.order_by("id").last()
        self.assertEqual(entrada.comentario, "La falla era eléctrica, no de redes.")
        self.assertEqual(entrada.estatus, EstatusTicket.FINALIZADO)

    def test_comentario_obligatorio(self):
        ticket = self._crear()
        asignar_ticket(ticket, self.admin_dti, self.tecnico_dti)
        with self.assertRaises(ErrorTicket):
            atender_ticket(ticket, self.tecnico_dti, "Visita realizada", EstatusTicket.PENDIENTE, "  ")

    def test_visto_bueno_del_solicitante_concluye_el_reporte(self):
        ticket = self._crear()
        asignar_ticket(ticket, self.admin_dti, self.tecnico_dti)
        atender_ticket(ticket, self.tecnico_dti, "Quedó operando", EstatusTicket.FINALIZADO, "Se probó con el usuario")
        with self.assertRaises(ErrorTicket):
            confirmar_visto_bueno(ticket, self.tecnico_dti)
        concluido = confirmar_visto_bueno(ticket, self.general)
        self.assertEqual(concluido.estatus, EstatusTicket.CONCLUIDO)
        estatuses = list(concluido.historial.order_by("id").values_list("estatus", flat=True))
        self.assertEqual(
            estatuses,
            [
                EstatusTicket.ABIERTO,
                EstatusTicket.ASIGNADO,
                EstatusTicket.FINALIZADO,
                EstatusTicket.VISTO_BUENO,
                EstatusTicket.CONCLUIDO,
            ],
        )

    def test_concluye_a_los_tres_dias_de_finalizado(self):
        ticket = self._crear()
        asignar_ticket(ticket, self.admin_dti, self.tecnico_dti)
        atender_ticket(ticket, self.tecnico_dti, "Listo", EstatusTicket.FINALIZADO, "Sin pendientes")
        ticket.fecha_finalizacion = timezone.now() - timedelta(days=3) + timedelta(minutes=5)
        ticket.save(update_fields=["fecha_finalizacion"])
        self.assertEqual(concluir_vencidos(), 0)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estatus, EstatusTicket.FINALIZADO)
        ticket.fecha_finalizacion = timezone.now() - timedelta(days=3, seconds=1)
        ticket.save(update_fields=["fecha_finalizacion"])
        self.assertEqual(concluir_vencidos(), 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estatus, EstatusTicket.CONCLUIDO)
        self.assertTrue(
            HistorialTicket.objects.filter(
                ticket=ticket,
                estatus=EstatusTicket.CONCLUIDO,
                atencion_brindada__startswith="Concluido automáticamente",
            ).exists()
        )
        call_command("concluir_tickets")


class PermisoVistaTests(BaseReportes):
    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse("tickets:lista"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuentas/entrar/", respuesta.url)

    def test_cada_rol_puede_crear_un_reporte(self):
        for usuario in (
            self.general,
            self.tecnico_dti,
            self.admin_dti,
            self.admin_sistema,
        ):
            self.client.force_login(usuario)
            respuesta = self.client.post(
                reverse("tickets:nuevo"),
                {
                    "area": self.daf.pk,
                    "extension": "220",
                    "descripcion": f"Falla reportada por {usuario.username} en el aula.",
                },
                follow=True,
            )
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, "SIS-DAF-RM-")

    def test_visibilidad_por_rol(self):
        propio = self._crear()
        ajeno = self._crear(creador=self.admin_daf, area=self.daf, descripcion="Falla en el almacén de materiales.")
        self.client.force_login(self.general)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[propio.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[ajeno.pk])).status_code, 404)
        self.client.force_login(self.admin_dti)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[propio.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[ajeno.pk])).status_code, 404)
        self.client.force_login(self.tecnico_dti)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[ajeno.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[propio.pk])).status_code, 404)
        self.client.force_login(self.admin_sistema)
        self.assertEqual(self.client.get(reverse("tickets:detalle", args=[ajeno.pk])).status_code, 200)

    def test_asignar_desde_la_vista(self):
        ticket = self._crear()
        self.client.force_login(self.general)
        self.assertEqual(
            self.client.post(reverse("tickets:asignar", args=[ticket.pk]), {"tecnico": self.tecnico_dti.pk}).status_code,
            403,
        )
        self.client.force_login(self.admin_daf)
        self.assertEqual(
            self.client.post(reverse("tickets:asignar", args=[ticket.pk]), {"tecnico": self.tecnico_daf.pk}).status_code,
            404,
        )
        self.client.force_login(self.admin_dti)
        rechazado = self.client.post(
            reverse("tickets:asignar", args=[ticket.pk]),
            {"tecnico": self.tecnico_daf.pk},
        )
        self.assertEqual(rechazado.status_code, 200)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.tecnico_asignado_id)
        respuesta = self.client.post(
            reverse("tickets:asignar", args=[ticket.pk]),
            {"tecnico": self.tecnico_dti.pk},
            follow=True,
        )
        self.assertContains(respuesta, "Se te ha sido asignado el tecnico: Carla Díaz")
        ticket.refresh_from_db()
        self.assertEqual(ticket.estatus, EstatusTicket.ASIGNADO)

    def test_atender_desde_la_vista(self):
        ticket = self._crear()
        asignar_ticket(ticket, self.admin_dti, self.tecnico_dti)
        self.client.force_login(self.tecnico_daf)
        self.assertEqual(
            self.client.post(
                reverse("tickets:atender", args=[ticket.pk]),
                {
                    "atencion_brindada": "Nada",
                    "nuevo_estatus": EstatusTicket.PENDIENTE,
                    "comentario": "No me corresponde",
                },
            ).status_code,
            403,
        )
        self.client.force_login(self.tecnico_dti)
        respuesta = self.client.post(
            reverse("tickets:atender", args=[ticket.pk]),
            {
                "atencion_brindada": "Se agenda la visita para mañana.",
                "nuevo_estatus": EstatusTicket.PENDIENTE,
                "comentario": "El laboratorio cierra hoy a las 15:00.",
            },
            follow=True,
        )
        self.assertContains(respuesta, "Se agenda la visita para mañana.")
        ticket.refresh_from_db()
        self.assertEqual(ticket.estatus, EstatusTicket.PENDIENTE)


class AdjuntoTests(BaseReportes):
    def test_rechaza_extension_tamano_e_imagen_invalida(self):
        class Archivo:
            def __init__(self, name, size):
                self.name = name
                self.size = size

        with self.assertRaises(ValidationError):
            validar_adjunto(Archivo("virus.exe", 20))
        with self.assertRaises(ValidationError):
            validar_adjunto(Archivo("grande.pdf", MAX_BYTES + 1))
        with self.assertRaises(ValidationError):
            validar_adjunto(SimpleUploadedFile("mal.png", b"no-es-imagen", content_type="image/png"))

    def test_sube_imagen_y_pdf_y_rechaza_el_resto(self):
        self.client.force_login(self.general)
        antes = Ticket.objects.count()
        invalido = self.client.post(
            reverse("tickets:nuevo"),
            {
                "area": self.dti.pk,
                "extension": "101",
                "descripcion": "Adjunto un ejecutable que no debe guardarse.",
                "adjuntos": SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream"),
            },
        )
        self.assertEqual(invalido.status_code, 200)
        self.assertEqual(Ticket.objects.count(), antes)
        valido = self.client.post(
            reverse("tickets:nuevo"),
            {
                "area": self.daf.pk,
                "extension": "101",
                "descripcion": "La pantalla del aula 3 queda en negro.",
                "adjuntos": [_png(), _pdf()],
            },
            follow=True,
        )
        self.assertEqual(valido.status_code, 200)
        ticket = Ticket.objects.latest("id")
        tipos = set(ticket.adjuntos.values_list("tipo", flat=True))
        self.assertEqual(tipos, {"imagen", "pdf"})
        self.assertEqual(AdjuntoTicket.objects.filter(ticket=ticket).count(), 2)
        self.client.force_login(self.tecnico_dti)
        prohibido = self.client.post(
            reverse("tickets:adjuntos", args=[ticket.pk]),
            {"adjuntos": _pdf("otro.pdf")},
        )
        self.assertEqual(prohibido.status_code, 403)


class ClaveConcurrenciaTests(TransactionTestCase):
    def test_varias_claves_simultaneas_no_se_repiten(self):
        area = Area.objects.create(
            codigo="VIC",
            subcodigo="PD",
            nombre="Prensa y Difusión",
            secuencia_anio=timezone.localdate().year,
            secuencia_actual=0,
        )
        barrera = threading.Barrier(5)
        claves = []
        errores = []

        def trabajador():
            try:
                connections.close_all()
                barrera.wait(timeout=15)
                with transaction.atomic():
                    claves.append(generar_clave(Area.objects.get(pk=area.pk)))
            except Exception as exc:
                errores.append(repr(exc))
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=trabajador) for _ in range(5)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=30)
            self.assertFalse(hilo.is_alive())
        self.assertEqual(errores, [])
        self.assertEqual(len(set(claves)), 5)
        area.refresh_from_db()
        self.assertEqual(area.secuencia_actual, 5)
