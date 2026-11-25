from django import forms

from apps.core.forms import EstiloFormMixin
from apps.core.models import Area
from apps.usuarios.models import Rol, Usuario

from .models import EstatusTicket
from .states import puede_transicionar


class TicketCrearForm(EstiloFormMixin, forms.Form):
    area = forms.ModelChoiceField(
        queryset=Area.objects.order_by("codigo", "subcodigo"),
        label="Área del reporte",
        empty_label="Selecciona un área",
        help_text="La clave usa la secuencia de esta área.",
    )
    extension = forms.CharField(max_length=20, label="Extensión")
    descripcion = forms.CharField(
        label="Descripción",
        widget=forms.Textarea,
        min_length=10,
    )

    def clean_extension(self):
        valor = self.cleaned_data["extension"].strip()
        if not valor:
            raise forms.ValidationError("La extensión es obligatoria.")
        return valor

    def clean_descripcion(self):
        valor = self.cleaned_data["descripcion"].strip()
        if len(valor) < 10:
            raise forms.ValidationError("La descripción debe tener al menos 10 caracteres.")
        return valor


class AsignarForm(EstiloFormMixin, forms.Form):
    tecnico = forms.ModelChoiceField(queryset=Usuario.objects.none(), label="Técnico del área")

    def __init__(self, *args, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tecnico"].queryset = Usuario.objects.filter(
            rol=Rol.TECNICO,
            area=area,
            is_active=True,
        ).order_by("first_name", "last_name", "username")
        self.fields["tecnico"].empty_label = "Selecciona un técnico"


class AtenderForm(EstiloFormMixin, forms.Form):
    atencion_brindada = forms.CharField(label="Atención brindada", widget=forms.Textarea)
    nuevo_estatus = forms.ChoiceField(label="Estatus", choices=())
    comentario = forms.CharField(label="Comentario", widget=forms.Textarea)

    def __init__(self, *args, ticket=None, **kwargs):
        super().__init__(*args, **kwargs)
        permitidos = []
        if ticket is not None:
            for valor, etiqueta in EstatusTicket.choices:
                if valor in {
                    EstatusTicket.PENDIENTE,
                    EstatusTicket.FINALIZADO,
                    EstatusTicket.CANCELADO,
                } and puede_transicionar(ticket.estatus, valor):
                    permitidos.append((valor, etiqueta))
        self.fields["nuevo_estatus"].choices = permitidos

    def clean_atencion_brindada(self):
        valor = self.cleaned_data["atencion_brindada"].strip()
        if not valor:
            raise forms.ValidationError("Describe la atención brindada.")
        return valor

    def clean_comentario(self):
        valor = self.cleaned_data["comentario"].strip()
        if not valor:
            raise forms.ValidationError("El comentario es obligatorio.")
        return valor
