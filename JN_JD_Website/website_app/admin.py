from django.contrib import admin
from .models import User, Role, Organization, Event, Group, EventGroups, UserGroups, UserOrganization

# Register the custom User model
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'f_name', 'l_name')  # Customize what is shown in the list view
    search_fields = ('username', 'f_name', 'l_name')  # Add search functionality

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'permissions')  # Display these fields in the list view
    search_fields = ('name',)  # Add search functionality by role name
    list_filter = ('name',)  # Optionally filter by role name

# Register the Organization model
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'date_created', 'owner', 'invite_code')  # Show name, creation date, owner, and invite code
    search_fields = ('name',)  # Allow searching by name
    list_filter = ('owner',)  # Filter by owner

# Register the Event model
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'location', 'organization', 'owner')  # Show event details
    search_fields = ('name', 'location')  # Allow searching by name and location
    list_filter = ('date', 'organization', 'owner')  # Filter by event date, organization, and owner

# Register the Group model
@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'date_created', 'organization', 'owner')  # Show group details
    search_fields = ('name',)  # Allow searching by name
    list_filter = ('organization', 'owner')  # Filter by organization and owner

# Register the EventGroups model
@admin.register(EventGroups)
class EventGroupsAdmin(admin.ModelAdmin):
    list_display = ('group', 'event')  # Show group and event associations
    search_fields = ('group__name', 'event__name')  # Allow searching by group and event names
    list_filter = ('group', 'event')  # Filter by group and event

# Register the UserGroups model
@admin.register(UserGroups)
class UserGroupsAdmin(admin.ModelAdmin):
    list_display = ('group', 'user')  # Show user-group associations
    search_fields = ('group__name', 'user__username')  # Allow searching by group and user names
    list_filter = ('group', 'user')  # Filter by group and user

# Register the UserOrganization model
@admin.register(UserOrganization)
class UserOrganizationAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization')  # Show user-organization associations
    search_fields = ('user__username', 'organization__name')  # Allow searching by user and organization names
    list_filter = ('organization',)  # Filter by organization
