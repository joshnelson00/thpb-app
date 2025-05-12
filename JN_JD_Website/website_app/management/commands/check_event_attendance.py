from django.core.management.base import BaseCommand
from django.utils import timezone
from website_app.models import Event, EventGroups, UserGroups, User
import math

class Command(BaseCommand):
    help = 'Checks attendance for events that are currently occurring'

    def handle(self, *args, **options):
        current_time = timezone.now()
        
        # Get all events that are currently happening
        active_events = Event.objects.filter(
            date__lte=current_time,
            date__gte=current_time - timezone.timedelta(hours=24)  # Check events from last 24 hours
        )

        for event in active_events:
            self.stdout.write(f"\nChecking attendance for event: {event.name}")
            
            # Get all groups assigned to this event
            event_groups = EventGroups.objects.filter(event=event)
            
            for event_group in event_groups:
                group = event_group.group
                self.stdout.write(f"\nGroup: {group.name}")
                
                # Get all users in this group
                group_users = UserGroups.objects.filter(group=group)
                
                for user_group in group_users:
                    user = user_group.user
                    
                    # Check if user has a location
                    if not user.latitude or not user.longitude:
                        self.stdout.write(f"  {user.username}: No location data available")
                        continue
                    
                    # Calculate distance between user and event
                    distance = self.calculate_distance(
                        user.latitude, user.longitude,
                        event.geofence_latitude, event.geofence_longitude
                    )
                    
                    if distance > event.geofence_radius:
                        self.stdout.write(f"  {user.username}: Not in attendance (Distance: {distance:.2f}m)")
                    else:
                        self.stdout.write(f"  {user.username}: Present (Distance: {distance:.2f}m)")

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the distance between two points using the Haversine formula
        Returns distance in meters
        """
        R = 6371000  # Earth's radius in meters
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Calculate differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c 