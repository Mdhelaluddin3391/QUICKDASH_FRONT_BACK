from django.core.management.base import BaseCommand
from apps.orders.models import Order
from apps.delivery.tasks import retry_auto_assign_rider


class Command(BaseCommand):
    help = "Retry rider assignment for unassigned orders"

    def handle(self, *args, **kwargs):
        orders = Order.objects.filter(
            status="confirmed",
            delivery__isnull=True,
        )

        for order in orders:
            retry_auto_assign_rider.delay(order.id)

        self.stdout.write("Retry tasks queued")
