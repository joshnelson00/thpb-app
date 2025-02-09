from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class User(AbstractUser):  
    f_name = models.CharField(max_length=255)  
    l_name = models.CharField(max_length=255)  
    is_admin = models.BooleanField(default=False)  

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

    class Meta:
        db_table = 'Organization'

class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateField()
    location = models.CharField(max_length=255, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='events')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_events')

    class Meta:
        db_table = 'Event'

class Group(models.Model):
    name = models.CharField(max_length=255)
    date_created = models.DateField(auto_now_add=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='groups')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='owned_groups')

    class Meta:
        db_table = 'Group'

class EventGroups(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='Group_ID', related_name='events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_column='Event_ID', related_name='groups')

    class Meta:
        db_table = 'EventGroups'
        unique_together = (('group', 'event'),)

class UserGroups(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='Group_ID', related_name='user_groups')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='User_ID', related_name='membership_groups')

    class Meta:
        db_table = 'UserGroups'
        unique_together = (('group', 'user'),)
