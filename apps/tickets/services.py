from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Area
from apps.usuarios.models import Rol

from .models import AdjuntoTicket, EstatusTicket, HistorialTicket, Ticket
from .states import puede_transicionar
from .validators import tipo_de_archivo, validar_adjunto


class ErrorTicket(Exception):
    pass


class TransicionInvalida(ErrorTicket):
    pass


def generar_clave(area: Area, anio: int | None = None) -> str:
    anio = anio or timezone.localdate().year
    if not transaction.get_connection().in_atomic_block:
        with transaction.atomic():
            return _generar_clave_bloqueada(area, anio)
    return _generar_clave_bloqueada(area, anio)


def _generar_clave_bloqueada(area: Area, anio: int) -> str:
    bloqueada = Area.objects.select_for_update().get(pk=area.pk)
    if bloqueada.secuencia_anio != anio:
        bloqueada.secuencia_anio = anio
        bloqueada.secuencia_actual = 0
    bloqueada.secuencia_actual += 1
    bloqueada.save(update_fields=["secuencia_anio", "secuencia_actual"])
    return (
        f"SIS-{bloqueada.codigo}-{bloqueada.subcodigo}-{anio}-R-"
        f"{bloqueada.secuencia_actual:09d}"
    )


def queryset_para(usuario):
    consulta = Ticket.objects.select_related(
        "creado_por",
        "creado_por__area",
        "area",
        "tecnico_asignado",
    )
    if not getattr(usuario, "is_authenticated", False):
        return consulta.none()
    if usuario.rol == Rol.ADMIN_SISTEMA:
        return consulta
    if usuario.rol == Rol.ADMIN_AREA:
        return consulta.filter(Q(area_id=usuario.area_id) | Q(creado_por=usuario))
    if usuario.rol == Rol.TECNICO:
        return consulta.filter(
            Q(creado_por=usuario) | Q(tecnico_asignado=usuario) | ~Q(area_id=usuario.area_id)
        )
    return consulta.filter(creado_por=usuario)


def puede_asignar(usuario, ticket) -> bool:
    return (
        usuario.rol == Rol.ADMIN_AREA
        and usuario.area_id == ticket.area_id
        and ticket.estatus == EstatusTicket.ABIERTO
    )


def puede_atender(usuario, ticket) -> bool:
    if usuario.rol != Rol.TECNICO or ticket.tecnico_asignado_id != usuario.id:
        return False
    return any(
        puede_transicionar(ticket.estatus, destino)
        for destino in (
            EstatusTicket.PENDIENTE,
            EstatusTicket.FINALIZADO,
            EstatusTicket.CANCELADO,
        )
    )


def puede_visto_bueno(usuario, ticket) -> bool:
    return usuario.pk == ticket.creado_por_id and ticket.estatus == EstatusTicket.FINALIZADO


def puede_adjuntar(usuario, ticket) -> bool:
    return usuario.pk == ticket.creado_por_id and ticket.estatus not in {
        EstatusTicket.CANCELADO,
        EstatusTicket.CONCLUIDO,
    }


def _validar_archivos(archivos):
    errores = []
    for archivo in archivos:
        try:
            validar_adjunto(archivo)
        except ValidationError as exc:
            errores.extend(exc.messages)
    if errores:
        raise ValidationError(errores)


def _guardar_adjuntos(ticket, usuario, archivos):
    for archivo in archivos:
        AdjuntoTicket.objects.create(
            ticket=ticket,
            archivo=archivo,
            tipo=tipo_de_archivo(archivo.name),
            subido_por=usuario,
        )


def _cambiar_estatus(ticket, nuevo, *, actor, atencion, comentario=""):
    if not puede_transicionar(ticket.estatus, nuevo):
        raise TransicionInvalida(
            f"No se puede pasar de {ticket.get_estatus_display()} a {EstatusTicket(nuevo).label}."
        )
    ticket.estatus = nuevo
    if nuevo == EstatusTicket.FINALIZADO:
        ticket.fecha_finalizacion = timezone.now()
    ticket.save()
    return HistorialTicket.objects.create(
        ticket=ticket,
        atencion_brindada=atencion,
        estatus=nuevo,
        creado_por=actor,
        comentario=comentario,
    )


def crear_ticket(*, creador, area, extension, descripcion, archivos=None) -> Ticket:
    archivos = list(archivos or [])
    extension = (extension or "").strip()
    descripcion = (descripcion or "").strip()
    if not extension:
        raise ValidationError("La extensión es obligatoria.")
    if len(descripcion) < 10:
        raise ValidationError("La descripción debe tener al menos 10 caracteres.")
    _validar_archivos(archivos)
    with transaction.atomic():
        ticket = Ticket.objects.create(
            clave=generar_clave(area),
            creado_por=creador,
            area=area,
            extension=extension,
            descripcion=descripcion,
            estatus=EstatusTicket.ABIERTO,
        )
        HistorialTicket.objects.create(
            ticket=ticket,
            atencion_brindada="Has generado el reporte",
            estatus=EstatusTicket.ABIERTO,
            creado_por=creador,
        )
        _guardar_adjuntos(ticket, creador, archivos)
    return ticket


def agregar_adjuntos(ticket, usuario, archivos):
    archivos = list(archivos or [])
    if usuario.pk != ticket.creado_por_id:
        raise ErrorTicket("Solo quien creó el reporte puede adjuntar archivos.")
    if not puede_adjuntar(usuario, ticket):
        raise ErrorTicket("Este reporte ya no admite archivos.")
    if not archivos:
        raise ValidationError("Selecciona al menos un archivo.")
    _validar_archivos(archivos)
    with transaction.atomic():
        _guardar_adjuntos(ticket, usuario, archivos)


def asignar_ticket(ticket, administrador, tecnico) -> Ticket:
    if administrador.rol != Rol.ADMIN_AREA:
        raise ErrorTicket("Solo el administrador de área asigna técnicos.")
    if administrador.area_id != ticket.area_id:
        raise ErrorTicket("Solo puedes asignar reportes de tu área.")
    if tecnico.rol != Rol.TECNICO or not tecnico.is_active:
        raise ErrorTicket("Selecciona un técnico activo.")
    if tecnico.area_id != administrador.area_id:
        raise ErrorTicket("El técnico debe pertenecer a tu área.")
    with transaction.atomic():
        bloqueado = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if bloqueado.area_id != administrador.area_id:
            raise ErrorTicket("Solo puedes asignar reportes de tu área.")
        bloqueado.tecnico_asignado = tecnico
        _cambiar_estatus(
            bloqueado,
            EstatusTicket.ASIGNADO,
            actor=administrador,
            atencion=f"Se te ha sido asignado el tecnico: {tecnico.nombre}",
        )
    return bloqueado


def atender_ticket(ticket, tecnico, atencion, nuevo_estatus, comentario) -> Ticket:
    if tecnico.rol != Rol.TECNICO:
        raise ErrorTicket("Solo un técnico registra la atención.")
    atencion = (atencion or "").strip()
    comentario = (comentario or "").strip()
    if not atencion:
        raise ErrorTicket("Describe la atención brindada.")
    if not comentario:
        raise ErrorTicket("El comentario es obligatorio.")
    if nuevo_estatus not in {
        EstatusTicket.PENDIENTE,
        EstatusTicket.FINALIZADO,
        EstatusTicket.CANCELADO,
    }:
        raise TransicionInvalida(
            "El técnico solo puede dejar el reporte pendiente, finalizado o cancelado."
        )
    with transaction.atomic():
        bloqueado = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if bloqueado.tecnico_asignado_id != tecnico.id:
            raise ErrorTicket("Solo el técnico asignado registra la atención.")
        # Un técnico atiende el reporte asignado aunque el área del reporte no sea la suya.
        _cambiar_estatus(
            bloqueado,
            nuevo_estatus,
            actor=tecnico,
            atencion=atencion,
            comentario=comentario,
        )
    return bloqueado


def confirmar_visto_bueno(ticket, usuario) -> Ticket:
    if usuario.pk != ticket.creado_por_id:
        raise ErrorTicket("Solo quien creó el reporte puede dar el visto bueno.")
    with transaction.atomic():
        bloqueado = Ticket.objects.select_for_update().get(pk=ticket.pk)
        if bloqueado.creado_por_id != usuario.pk:
            raise ErrorTicket("Solo quien creó el reporte puede dar el visto bueno.")
        _cambiar_estatus(
            bloqueado,
            EstatusTicket.VISTO_BUENO,
            actor=usuario,
            atencion="Visto bueno: la asistencia finalizó correctamente.",
        )
        _cambiar_estatus(
            bloqueado,
            EstatusTicket.CONCLUIDO,
            actor=usuario,
            atencion="El reporte quedó concluido con el visto bueno del solicitante.",
        )
    return bloqueado


def concluir_vencidos(ahora=None) -> int:
    ahora = ahora or timezone.now()
    limite = ahora - timedelta(days=3)
    identificadores = list(
        Ticket.objects.filter(
            estatus=EstatusTicket.FINALIZADO,
            fecha_finalizacion__isnull=False,
            fecha_finalizacion__lte=limite,
        ).values_list("pk", flat=True)
    )
    total = 0
    for identificador in identificadores:
        with transaction.atomic():
            bloqueado = Ticket.objects.select_for_update().get(pk=identificador)
            if bloqueado.estatus != EstatusTicket.FINALIZADO or not bloqueado.fecha_finalizacion:
                continue
            if bloqueado.fecha_finalizacion > limite:
                continue
            actor = bloqueado.tecnico_asignado or bloqueado.creado_por
            _cambiar_estatus(
                bloqueado,
                EstatusTicket.CONCLUIDO,
                actor=actor,
                atencion="Concluido automáticamente: pasaron 3 días desde la finalización.",
            )
            total += 1
    return total
