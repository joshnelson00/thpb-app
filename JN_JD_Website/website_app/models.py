from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import random
import string

class User(AbstractUser):
    f_name = models.CharField(max_length=255)
    l_name = models.CharField(max_length=255)

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
    permissions = models.CharField(max_length=255, blank=True, null=True)  # Store specific permissions

    class Meta:
        db_table = 'Role'
    
    def __str__(self):
        return self.name

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateField()
    location = models.CharField(max_length=255, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='events')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_events')

    def get_attending_groups(self):
        return self.groups.all()

    class Meta:
        db_table = 'Event'

class Group(models.Model):
    name = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='groups')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_groups')

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