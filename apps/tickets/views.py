from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import Area
from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import rol_requerido

from .forms import AsignarForm, AtenderForm, TicketCrearForm
from .models import EstatusTicket, Ticket
from .services import (
    ErrorTicket,
    TransicionInvalida,
    agregar_adjuntos,
    asignar_ticket,
    atender_ticket,
    confirmar_visto_bueno,
    crear_ticket,
    puede_adjuntar,
    puede_asignar,
    puede_atender,
    puede_visto_bueno,
    queryset_para,
)
from .states import AYUDA_ESTATUS


def _ticket_visible(usuario, pk):
    return get_object_or_404(
        queryset_para(usuario).prefetch_related("adjuntos", "historial__creado_por"),
        pk=pk,
    )


def _contexto_detalle(usuario, ticket, asignar_form=None, atender_form=None):
    return {
        "ticket": ticket,
        "historial": ticket.historial.select_related("creado_por"),
        "asignar_form": asignar_form or AsignarForm(area=ticket.area),
        "atender_form": atender_form or AtenderForm(ticket=ticket),
        "puede_asignar": puede_asignar(usuario, ticket),
        "puede_atender": puede_atender(usuario, ticket),
        "puede_visto_bueno": puede_visto_bueno(usuario, ticket),
        "puede_adjuntar": puede_adjuntar(usuario, ticket),
        "hay_tecnicos": Usuario.objects.filter(
            rol=Rol.TECNICO,
            area=ticket.area,
            is_active=True,
        ).exists(),
        "ayuda": AYUDA_ESTATUS.get(ticket.estatus, ""),
    }


@login_required
def lista(request):
    base = queryset_para(request.user)
    conteos = {valor: 0 for valor, _etiqueta in EstatusTicket.choices}
    for fila in base.values("estatus").annotate(total=Count("id")):
        conteos[fila["estatus"]] = fila["total"]
    resumen = [
        {"valor": valor, "etiqueta": etiqueta, "total": conteos[valor]}
        for valor, etiqueta in EstatusTicket.choices
    ]
    consulta = base
    estatus = request.GET.get("estatus", "")
    area = request.GET.get("area", "")
    tecnico = request.GET.get("tecnico", "")
    if estatus in EstatusTicket.values:
        consulta = consulta.filter(estatus=estatus)
    if area.isdigit():
        consulta = consulta.filter(area_id=int(area))
    if tecnico.isdigit():
        consulta = consulta.filter(tecnico_asignado_id=int(tecnico))
    pagina = Paginator(consulta, 20).get_page(request.GET.get("page"))
    areas = Area.objects.filter(pk__in=base.values("area_id")).order_by("codigo", "subcodigo")
    tecnicos = Usuario.objects.filter(
        pk__in=base.exclude(tecnico_asignado__isnull=True).values("tecnico_asignado_id")
    ).order_by("first_name", "username")
    return render(
        request,
        "tickets/ticket_list.html",
        {
            "pagina": pagina,
            "resumen": resumen,
            "estatuses": EstatusTicket.choices,
            "areas": areas,
            "tecnicos": tecnicos,
        },
    )


@login_required
def nuevo(request):
    if request.method == "POST":
        form = TicketCrearForm(request.POST)
        if form.is_valid():
            try:
                ticket = crear_ticket(
                    creador=request.user,
                    area=form.cleaned_data["area"],
                    extension=form.cleaned_data["extension"],
                    descripcion=form.cleaned_data["descripcion"],
                    archivos=request.FILES.getlist("adjuntos"),
                )
            except ValidationError as exc:
                for mensaje in exc.messages:
                    form.add_error(None, mensaje)
            else:
                messages.success(request, f"Reporte {ticket.clave} creado.")
                return redirect("tickets:detalle", pk=ticket.pk)
    else:
        if not Area.objects.exists():
            messages.error(request, "No hay áreas. Un administrador debe ejecutar seed_areas.")
            return redirect("tickets:lista")
        form = TicketCrearForm(
            initial={
                "extension": request.user.extension,
                "area": request.user.area_id,
            }
        )
    return render(request, "tickets/ticket_form.html", {"form": form})


@login_required
def detalle(request, pk):
    ticket = _ticket_visible(request.user, pk)
    return render(request, "tickets/ticket_detail.html", _contexto_detalle(request.user, ticket))


@rol_requerido(Rol.ADMIN_AREA)
@require_POST
def asignar(request, pk):
    ticket = _ticket_visible(request.user, pk)
    form = AsignarForm(request.POST, area=ticket.area)
    if form.is_valid():
        try:
            asignar_ticket(ticket, request.user, form.cleaned_data["tecnico"])
        except (ErrorTicket, TransicionInvalida) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Técnico asignado.")
            return redirect("tickets:detalle", pk=ticket.pk)
    else:
        messages.error(request, "Revisa el técnico seleccionado.")
    ticket = _ticket_visible(request.user, pk)
    return render(
        request,
        "tickets/ticket_detail.html",
        _contexto_detalle(request.user, ticket, asignar_form=form),
    )


@rol_requerido(Rol.TECNICO)
@require_POST
def atender(request, pk):
    ticket = _ticket_visible(request.user, pk)
    if ticket.tecnico_asignado_id != request.user.id:
        raise PermissionDenied("Solo el técnico asignado registra la atención.")
    form = AtenderForm(request.POST, ticket=ticket)
    if form.is_valid():
        try:
            atender_ticket(
                ticket,
                request.user,
                form.cleaned_data["atencion_brindada"],
                form.cleaned_data["nuevo_estatus"],
                form.cleaned_data["comentario"],
            )
        except (ErrorTicket, TransicionInvalida) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Atención registrada.")
            return redirect("tickets:detalle", pk=ticket.pk)
    ticket = _ticket_visible(request.user, pk)
    return render(
        request,
        "tickets/ticket_detail.html",
        _contexto_detalle(request.user, ticket, atender_form=form),
    )


@login_required
@require_POST
def visto_bueno(request, pk):
    ticket = _ticket_visible(request.user, pk)
    try:
        confirmar_visto_bueno(ticket, request.user)
    except (ErrorTicket, TransicionInvalida) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Visto bueno registrado. El reporte quedó concluido.")
    return redirect("tickets:detalle", pk=ticket.pk)


@login_required
@require_POST
def adjuntos(request, pk):
    ticket = _ticket_visible(request.user, pk)
    if request.user.pk != ticket.creado_por_id:
        raise PermissionDenied("Solo quien creó el reporte puede adjuntar archivos.")
    archivos = request.FILES.getlist("adjuntos")
    try:
        agregar_adjuntos(ticket, request.user, archivos)
    except (ErrorTicket, ValidationError) as exc:
        mensajes = exc.messages if isinstance(exc, ValidationError) else [str(exc)]
        for mensaje in mensajes:
            messages.error(request, mensaje)
    else:
        messages.success(request, "Archivos adjuntados.")
    return redirect("tickets:detalle", pk=ticket.pk)
