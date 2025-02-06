from django.db import models

class Organization(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    date_created = models.DateTimeField(auto_now_add=True)  # Automatically set when created
    owner = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='owned_organizations') 

    class Meta:
        managed = False
        db_table = 'Organization'

class User(models.Model):
    id = models.IntegerField(primary_key=True)
    f_name = models.CharField(max_length=255)
    l_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)  # Ensure email uniqueness
    username = models.CharField(max_length=255, unique=True)  # Ensure username uniqueness
    password = models.CharField(max_length=255) 
    date_joined = models.DateTimeField(auto_now_add=True)  # Automatically set when created
    organizations = models.ManyToManyField(Organization, related_name='users')
    is_admin = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = 'User'

class Event(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    date_time = models.DateTimeField()
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='events')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_events') 

    class Meta:
        managed = False
        db_table = 'Event'

class Group(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    date_created = models.DateTimeField(auto_now_add=True)  # Automatically set when created
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='groups')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_groups')

    class Meta:
        managed = False
        db_table = 'Group'

class EventGroups(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='Group_ID', related_name='events')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_column='Event_ID', related_name='groups')

    class Meta:
        managed = False
        db_table = 'EventGroups'
        unique_together = (('group', 'event'),)

class UserGroups(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='Group_ID', related_name='users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='User_ID', related_name='groups')

    class Meta:
        managed = False
        db_table = 'UserGroups'
        unique_together = (('group', 'user'),)