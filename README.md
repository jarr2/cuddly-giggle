# SIS — reportes

Sistema de incidencias con Django, entorno [uv](https://docs.astral.sh/uv/) y MariaDB en Docker.

## Arranque

```bash
docker compose up -d
uv sync
uv run python manage.py migrate
uv run python manage.py seed_areas
uv run python manage.py runserver
```

Entra en http://127.0.0.1:8000/cuentas/entrar/

Usuarios de demostración (contraseña `Demo12345` si el seed los acaba de crear): `general`, `gestor`, `tecnico.ss`, `admin.ss`, `admin`.

`admin` también entra a `/admin/` para áreas y centros de cómputo.

## Pruebas

```bash
uv run python manage.py test
```

## Cierre automático

Los reportes en estatus finalizado pasan a concluido a los 3 días:

```bash
uv run python manage.py concluir_tickets
```
