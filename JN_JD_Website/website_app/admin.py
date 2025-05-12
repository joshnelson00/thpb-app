from django.contrib import admin
from .models import (
    User, Role, Organization, Event, Group, EventGroups, UserGroups, UserOrganization,
    EventCheckIn, EventAttendance, Announcement, AnnouncementFile, EventAttendees,
    EventSubstitution, SubstitutionRequest
)

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

# Register the EventCheckIn model
@admin.register(EventCheckIn)
class EventCheckInAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'check_in_time', 'is_within_radius')
    search_fields = ('user__username', 'event__name')
    list_filter = ('is_within_radius', 'check_in_time', 'event')

# Register the EventAttendance model
@admin.register(EventAttendance)
class EventAttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'check_in_time', 'is_attending')
    search_fields = ('user__username', 'event__name')
    list_filter = ('is_attending', 'check_in_time', 'event')

# Register the Announcement model
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'created_by', 'created_at', 'is_active')
    search_fields = ('title', 'content', 'organization__name')
    list_filter = ('is_active', 'created_at', 'organization')
    date_hierarchy = 'created_at'

# Register the AnnouncementFile model
@admin.register(AnnouncementFile)
class AnnouncementFileAdmin(admin.ModelAdmin):
    list_display = ('filename', 'announcement', 'uploaded_at')
    search_fields = ('filename', 'announcement__title')
    list_filter = ('uploaded_at', 'announcement')

# Register the EventAttendees model
@admin.register(EventAttendees)
class EventAttendeesAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'group', 'date_added')
    search_fields = ('user__username', 'event__name', 'group__name')
    list_filter = ('date_added', 'event', 'group')

# Register the EventSubstitution model
@admin.register(EventSubstitution)
class EventSubstitutionAdmin(admin.ModelAdmin):
    list_display = ('event', 'original_user', 'substitute_user', 'date_created')
    search_fields = ('event__name', 'original_user__username', 'substitute_user__username')
    list_filter = ('date_created', 'event')

# Register the SubstitutionRequest model
@admin.register(SubstitutionRequest)
class SubstitutionRequestAdmin(admin.ModelAdmin):
    list_display = ('event', 'requesting_user', 'target_user', 'status', 'created_at')
    search_fields = ('event__name', 'requesting_user__username', 'target_user__username')
    list_filter = ('status', 'created_at', 'event')
    date_hierarchy = 'created_at'
