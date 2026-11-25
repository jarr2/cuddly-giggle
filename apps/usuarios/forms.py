from django.contrib.auth.password_validation import validate_password
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from apps.core.forms import EstiloFormMixin
from apps.core.models import Area

from .models import Rol, Usuario


class AccesoForm(EstiloFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuario"
        self.fields["password"].label = "Contraseña"


class UsuarioForm(EstiloFormMixin, forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Obligatoria al crear. En edición, déjala vacía para conservarla.",
    )

    class Meta:
        model = Usuario
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "rol",
            "area",
            "extension",
            "telefono",
            "is_active",
        ]
        labels = {
            "username": "Usuario",
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo",
            "is_active": "Activo",
        }

    def __init__(self, *args, editor=None, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = Area.objects.order_by("codigo", "subcodigo")
        self.fields["area"].empty_label = "Sin área"
        self.fields["area"].required = False
        if not self.instance.pk:
            self.fields["is_active"].initial = True

    def clean_first_name(self):
        valor = self.cleaned_data["first_name"].strip()
        if not valor:
            raise forms.ValidationError("El nombre es obligatorio.")
        return valor

    def clean_last_name(self):
        valor = self.cleaned_data["last_name"].strip()
        if not valor:
            raise forms.ValidationError("Los apellidos son obligatorios.")
        return valor

    def clean(self):
        limpio = super().clean()
        password = limpio.get("password")
        if not self.instance.pk and not password:
            self.add_error("password", "La contraseña es obligatoria.")
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        if limpio.get("rol") in {Rol.TECNICO, Rol.ADMIN_AREA} and limpio.get("area") is None:
            self.add_error("area", "Este rol requiere un área.")
        editor = self.editor
        if editor and self.instance.pk == editor.pk:
            if limpio.get("rol") != Rol.ADMIN_SISTEMA:
                self.add_error("rol", "No puedes quitarte el rol de administrador de sistema.")
            if not limpio.get("is_active"):
                self.add_error("is_active", "No puedes desactivar tu propio usuario.")
        return limpio

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            usuario.set_password(password)
        if commit:
            usuario.save()
        return usuario


class PerfilForm(EstiloFormMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "extension", "telefono"]
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo",
            "extension": "Extensión",
            "telefono": "Teléfono",
        }

    def clean_first_name(self):
        valor = self.cleaned_data["first_name"].strip()
        if not valor:
            raise forms.ValidationError("El nombre es obligatorio.")
        return valor

    def clean_last_name(self):
        valor = self.cleaned_data["last_name"].strip()
        if not valor:
            raise forms.ValidationError("Los apellidos son obligatorios.")
        return valor


class ContrasenaForm(EstiloFormMixin, PasswordChangeForm):
    pass
