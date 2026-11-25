from django.core.management.base import BaseCommand

from apps.tickets.services import concluir_vencidos


class Command(BaseCommand):
    help = "Concluye reportes finalizados hace 3 días o más."

    def handle(self, *args, **options):
        total = concluir_vencidos()
        self.stdout.write(self.style.SUCCESS(f"Reportes concluidos: {total}"))
