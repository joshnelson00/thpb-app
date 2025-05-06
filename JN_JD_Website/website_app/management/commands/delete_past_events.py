from django.core.management.base import BaseCommand
from website_app.models import Event
from django.utils.timezone import now

class Command(BaseCommand):
    help = 'Deletes events whose date has passed'

    def handle(self, *args, **kwargs):
        past_events = Event.objects.filter(date__lt=now().date())
        count = past_events.count()
        past_events.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} past event(s)."))
