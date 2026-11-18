from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from m1.models import Conversation


class Command(BaseCommand):
    help = "Close conversations 24 hours after their trip departure."

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Conversation.objects.filter(
            closed_at__isnull=True,
            departure_at__lte=now - timedelta(hours=24),
        )
        count = expired.update(
            closed_at=now,
            close_reason=Conversation.CloseReason.EXPIRED,
        )
        self.stdout.write(f"Closed {count} conversation(s).")
