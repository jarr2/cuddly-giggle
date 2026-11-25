from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

IMAGENES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DOCUMENTOS = {".pdf", ".xls", ".xlsx", ".doc", ".docx"}
PERMITIDAS = IMAGENES | DOCUMENTOS
MAX_BYTES = 10 * 1024 * 1024

TIPOS = {
    ".jpg": "imagen",
    ".jpeg": "imagen",
    ".png": "imagen",
    ".gif": "imagen",
    ".webp": "imagen",
    ".pdf": "pdf",
    ".xls": "excel",
    ".xlsx": "excel",
    ".doc": "word",
    ".docx": "word",
}


def tipo_de_archivo(nombre: str) -> str:
    return TIPOS.get(Path(nombre).suffix.lower(), "")


def validar_adjunto(archivo):
    nombre = Path(getattr(archivo, "name", "")).name
    extension = Path(nombre).suffix.lower()
    if extension not in PERMITIDAS:
        raise ValidationError(
            f"El archivo {nombre or 'sin nombre'} no está permitido. Usa imagen, PDF, Excel o Word."
        )
    tamano = getattr(archivo, "size", None)
    if tamano is None:
        raise ValidationError(f"No se pudo leer el tamaño de {nombre}.")
    if tamano <= 0:
        raise ValidationError(f"El archivo {nombre} está vacío.")
    if tamano > MAX_BYTES:
        raise ValidationError(f"El archivo {nombre} supera 10 MB.")
    if extension in IMAGENES:
        try:
            imagen = Image.open(archivo)
            imagen.verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValidationError(f"La imagen {nombre} no es válida.") from exc
        finally:
            if hasattr(archivo, "seek"):
                archivo.seek(0)
