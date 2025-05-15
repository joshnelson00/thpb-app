from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import random
import string
from django.utils import timezone

class User(AbstractUser):
    f_name = models.CharField(max_length=255)
    l_name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    tag = models.ForeignKey('Tag', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="custom_user_set",  # Prevents conflict with Django's built-in User.groups
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="custom_user_permissions_set",  # Prevents conflict with Django's built-in User.user_permissions
        blank=True,
    )

    class Meta:
        db_table = 'User'

class Organization(models.Model):
    name = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_organizations')
    invite_code = models.CharField(max_length=10, unique=True, blank=True, null=True)  # Unique 10-character code

    class Meta:
        db_table = 'Organization'

    def save(self, *args, **kwargs):
        if not self.invite_code:  # Only generate if it doesn't exist
            self.invite_code = self.generate_unique_invite_code()
        super().save(*args, **kwargs)

    def generate_unique_invite_code(self):
        """Generate a unique random 10-character invite code."""
        while True:
            code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            if not Organization.objects.filter(invite_code=code).exists():
                return code

    def __str__(self):
        return self.name

class Role(models.Model):
    name = models.CharField(max_length=255)  # Role name (e.g., Admin, Manager, Member)
    permissions = models.CharField(max_length=255, blank=True)  # Store specific permissions

    class Meta:
        db_table = 'Role'
    
    def __str__(self):
        return self.name

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateField()
    time = models.TimeField(default=timezone.datetime.min.time())
    location = models.CharField(max_length=255, default='No location specified')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='events')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_events')
    # Geofence fields
    geofence_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geofence_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geofence_radius = models.PositiveIntegerField(null=True, blank=True, help_text="Radius in meters")
    # Timezone field
    timezone = models.CharField(max_length=50, default='America/New_York')

    def get_attending_users(self):
        return self.attendees.all()

    def get_attending_groups(self):
        return self.groups.all()

    class Meta:
        db_table = 'Event'

class Group(models.Model):
    name = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='groups')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_groups')
    color = models.CharField(max_length=7, default='#6666ff')  # Default to medium-blue-slate

    class Meta:
        db_table = 'Group'
        
    def __str__(self):
        return self.name  # Ensure that the group name is returned here

class EventGroups(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='Group_ID', related_name='events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_column='Event_ID', related_name='groups')

    class Meta:
        db_table = 'EventGroups'
        unique_together = (('group', 'event'),)

class UserGroups(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='Group_ID', related_name='user_groups')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='User_ID', related_name='membership_groups')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, related_name='user_groups')  # Add role for user in the group

    class Meta:
        db_table = 'UserGroups'
        unique_together = (('group', 'user'),)

class UserEvents(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='User_ID', related_name='user_events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_column='Event_ID', related_name='user_events')
    date_joined = models.DateField(auto_now_add=True)  # Store the date the user joined the event

    class Meta:
        db_table = 'UserEvents'
        unique_together = (('user', 'event'),)

class UserOrganization(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='User_ID', related_name='user_organizations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, db_column='Organization_ID', related_name='user_organizations')

class Geofence(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius = models.PositiveIntegerField(help_text="Radius in meters")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='geofences')
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_geofences')

    class Meta:
        db_table = 'Geofence'
        
    def __str__(self):
        return f"{self.name} - {self.event.name}"

class EventCheckIn(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_checkins')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='checkins')
    check_in_time = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_within_radius = models.BooleanField(default=False)

    class Meta:
        db_table = 'EventCheckIn'
        unique_together = (('user', 'event'),)

    def __str__(self):
        return f"{self.user.username} - {self.event.name} - {self.check_in_time}"

class EventAttendance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_attendance')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendance')
    check_in_time = models.DateTimeField(null=True, blank=True)
    is_attending = models.BooleanField(default=False)

    class Meta:
        db_table = 'EventAttendance'
        unique_together = (('user', 'event'),)

    def __str__(self):
        return f"{self.user.username} - {self.event.name} - {'Attended' if self.is_attending else 'Not Attended'}"

class Announcement(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_announcements')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'Announcement'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.organization.name} - {self.title}"

# TODO: AWS S3 Implementation Steps
# 1. Install required packages:
#    pip install django-storages boto3
#
# 2. Update settings.py with AWS configuration:
#    INSTALLED_APPS += ['storages']
#    AWS_ACCESS_KEY_ID = 'your-access-key'
#    AWS_SECRET_ACCESS_KEY = 'your-secret-key'
#    AWS_STORAGE_BUCKET_NAME = 'your-bucket-name'
#    AWS_S3_REGION_NAME = 'your-region'
#    AWS_DEFAULT_ACL = 'private'
#    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
#    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
#
# 3. Create custom storage class for announcement files
# 4. Update file field to use S3 storage
# 5. Set up proper IAM roles and bucket policies
# 6. Configure CORS if needed for direct uploads
# 7. Consider implementing signed URLs for secure file access

class AnnouncementFile(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='announcement_files/')
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'AnnouncementFile'

    def __str__(self):
        return self.filename

class EventAttendees(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attending_events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendees')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='event_attendees', null=True)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'EventAttendees'
        unique_together = (('user', 'event'),)

    def __str__(self):
        return f"{self.user.username} - {self.event.name}"

class EventSubstitution(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='substitutions')
    original_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='substituted_out')
    substitute_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='substituted_in')
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_substitutions')

    class Meta:
        db_table = 'EventSubstitution'
        unique_together = (('event', 'original_user'),)

    def __str__(self):
        return f"{self.original_user.get_full_name()} → {self.substitute_user.get_full_name()} for {self.event.name}"

class SubstitutionRequest(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='substitution_requests')
    requesting_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='substitution_requests_made')
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='substitution_requests_received')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'SubstitutionRequest'
        unique_together = (('event', 'requesting_user', 'target_user'),)

    def __str__(self):
        return f"{self.requesting_user.get_full_name()} → {self.target_user.get_full_name()} for {self.event.name}"

class Tag(models.Model):
    name = models.CharField(max_length=255)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tags')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tags')
    date_created = models.DateTimeField(auto_now_add=True)
    color = models.CharField(max_length=7, default='#6666ff')  # Default to medium-blue-slate

    class Meta:
        db_table = 'Tag'
        unique_together = (('name', 'organization'),)  # Tag names must be unique within an organization

    def __str__(self):
        return self.name
