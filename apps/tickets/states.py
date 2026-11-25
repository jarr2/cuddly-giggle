from .models import EstatusTicket

TRANSICIONES = {
    EstatusTicket.ABIERTO: {EstatusTicket.ASIGNADO},
    EstatusTicket.ASIGNADO: {
        EstatusTicket.PENDIENTE,
        EstatusTicket.FINALIZADO,
        EstatusTicket.CANCELADO,
    },
    EstatusTicket.PENDIENTE: {EstatusTicket.FINALIZADO, EstatusTicket.CANCELADO},
    EstatusTicket.FINALIZADO: {EstatusTicket.VISTO_BUENO, EstatusTicket.CONCLUIDO},
    EstatusTicket.VISTO_BUENO: {EstatusTicket.CONCLUIDO},
    EstatusTicket.CANCELADO: set(),
    EstatusTicket.CONCLUIDO: set(),
}

AYUDA_ESTATUS = {
    EstatusTicket.ABIERTO: "El reporte se generó y todavía no tiene técnico asignado.",
    EstatusTicket.ASIGNADO: "El reporte tiene un técnico asignado.",
    EstatusTicket.PENDIENTE: "El técnico dejó el reporte pendiente, por ejemplo para agendar la asistencia.",
    EstatusTicket.FINALIZADO: "El técnico terminó la asistencia. Quien lo solicitó puede dar el visto bueno.",
    EstatusTicket.CANCELADO: "La asistencia se canceló o la solicitud no corresponde al área.",
    EstatusTicket.CONCLUIDO: "El reporte quedó concluido por visto bueno o porque pasaron 3 días desde la finalización.",
    EstatusTicket.VISTO_BUENO: "Quien solicitó el reporte confirmó que la asistencia finalizó correctamente.",
}


def puede_transicionar(origen, destino) -> bool:
    return destino in TRANSICIONES.get(origen, set())
