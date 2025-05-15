from django.utils.timezone import now
from django.contrib import messages
import time, json
from datetime import datetime, time as datetime_time

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignInForm, CreateAccountForm, CreateOrganizationForm, CreateGroupForm, CreateEventForm, JoinOrganizationForm, CreateGeofenceForm
from django.views.decorators.csrf import csrf_exempt
from .models import Organization, Event, UserGroups, EventGroups, UserOrganization, Group, User, EventCheckIn, EventAttendance, Announcement, AnnouncementFile, EventAttendees, EventSubstitution, SubstitutionRequest, Tag
from django.http import Http404
from django.conf import settings
from django.views.decorators.http import require_POST
from django.utils import timezone
import math
from django.db.models import Q, Count
import pytz
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
import csv
from django.http import HttpResponse
from django.urls import reverse



@login_required
def home(request):
    # Get organizations owned by the user
    owned_organizations = Organization.objects.filter(owner=request.user)
    
    # Get organizations where user is a member (but not owner)
    member_organizations = Organization.objects.filter(
        user_organizations__user=request.user
    ).exclude(owner=request.user)
    
    # Get all organizations user has access to
    organizations = owned_organizations | member_organizations
    
    # Base query for events - same as view_events
    events_query = Event.objects.filter(
        Q(attendees__user=request.user) |  # Events where user is an attendee
        Q(organization__in=organizations)  # Events from organizations user owns or is a member of
    ).distinct()
    
    # Get current time in UTC
    current_time = timezone.now()
    
    # Get all events and filter them in Python to handle timezone conversions properly
    all_events = events_query.order_by('date', 'time')
    upcoming_events = []
    
    for event in all_events:
        # Get the event's timezone
        event_tz = pytz.timezone(event.timezone)
        
        # Create a datetime object in the event's timezone
        event_datetime = timezone.datetime.combine(event.date, event.time)
        event_datetime = event_tz.localize(event_datetime)
        
        # Get current time in the event's timezone
        current_time_tz = current_time.astimezone(event_tz)
        
        # Calculate time difference
        time_until = event_datetime - current_time_tz
        minutes_until = int(time_until.total_seconds() / 60)
        
        # Only include events that haven't started yet or are within the check-in window
        if minutes_until > -5:  # Changed from > 0 to > -5 to include events in progress
            event.minutes_until = minutes_until
            # Set can_check_in property - allow check-in 30 minutes before and 5 minutes after event
            event.can_check_in = -5 <= minutes_until <= 30
            # Set is_concluded property - event is concluded if it's more than 5 minutes past start time
            event.is_concluded = minutes_until < -5
            # Check if user has already checked in
            event.user_check_in = EventCheckIn.objects.filter(
                user=request.user,
                event=event,
                is_within_radius=True
            ).exists()
            # Get attending groups for the event
            event.attending_groups = [{'name': event_group.group.name, 'color': event_group.group.color} for event_group in event.groups.all()]
            
            # Calculate time display
            if minutes_until >= 1440:  # More than 24 hours
                days = minutes_until // 1440
                remaining_minutes = minutes_until % 1440
                hours = remaining_minutes // 60
                event.time_display = f"{days}d {hours}h"
            elif minutes_until >= 60:  # More than 1 hour
                hours = minutes_until // 60
                minutes = minutes_until % 60
                event.time_display = f"{hours}h {minutes}m"
            else:
                event.time_display = f"{minutes_until}m"
            
            # Check if user is attending this event
            event.user_can_attend = EventAttendees.objects.filter(event=event, user=request.user).exists()
            
            upcoming_events.append(event)
            
            # Break after getting 3 events
            if len(upcoming_events) >= 3:
                break

    # Get user's groups with their roles
    user_groups = UserGroups.objects.filter(user=request.user).select_related('group', 'group__organization')

    # Get all announcements from organizations the user has access to
    announcements = Announcement.objects.filter(
        organization__in=organizations,
        is_active=True
    ).select_related('created_by', 'organization').prefetch_related('files').order_by('-created_at')[:5]

    context = {
        'upcoming_events': upcoming_events,
        'user_groups': user_groups,
        'owned_organizations': owned_organizations,
        'member_organizations': member_organizations,
        'announcements': announcements,
    }
    return render(request, 'home.html', context)

@login_required
def about(request):
    # About page context, you can update it if necessary
    context = {}
    return render(request, 'index.html', context)

def create_account(request):
    if request.method == "POST":
        form = CreateAccountForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)  # Create user but don't save yet
            user.save()  # Now save the user after modifying if needed

            auth_login(request, user)  # Log in the newly created user

            # Handle 'remember me' functionality
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)  # Session expires on browser close
            print(f"User created: {user.username}")
            print(request.user)
            return redirect('home')  # Redirect to homepage after successful signup
    else:
        form = CreateAccountForm()  # Instantiate an empty form if GET request

    return render(request, 'createaccount.html', {'form': form})


def sign_in(request):
    if request.method == "POST":
        form = SignInForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
    
            if user is not None:
                auth_login(request, user)

                # Handle 'remember me' functionality
                if not form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(0)
                return redirect('home')
            else:
                # Check if username exists
                username = form.cleaned_data.get('username')
                if User.objects.filter(username=username).exists():
                    form.add_error(None, "Incorrect password. Please try again.")
                else:
                    form.add_error(None, "No account found with this username. Please check your username or create a new account.")
        else:
            # Handle specific form errors
            if 'username' in form.errors:
                form.add_error(None, "Please enter a valid username.")
            elif 'password' in form.errors:
                form.add_error(None, "Please enter your password.")
            else:
                form.add_error(None, "Please check your username and password and try again.")
    else:
        form = SignInForm()

    context = {
        'form': form
    }
    return render(request, 'signin.html', context)

@login_required
def edit_groups(request, org_id):
    # Fetch the organization or raise a 404 if not found
    organization = get_object_or_404(Organization, id=org_id, owner=request.user)
    
    # Get all groups in the organization
    groups = organization.groups.all()

    # Create a dictionary that holds the users in each group
    users_in_groups = {}
    for group in groups:
        # Get the UserGroups objects for this group
        users_in_groups[group.id] = group.user_groups.select_related('user').all()

    org_users = organization.user_organizations.values_list('user', flat=True)
    
    # Get users who are not in any group in this organization
    users_not_in_groups = User.objects.filter(
        id__in=org_users
    ).exclude(
        id__in=UserGroups.objects.filter(
            group__organization=organization
        ).values_list('user_id', flat=True)
    )

    # Handle form submission for adding/removing users from groups
    if request.method == "POST":
        user_id = request.POST.get('user_id')
        group_id = request.POST.get('group_id')
        action = request.POST.get('action')
        role = request.POST.get('role', None)  # Optional: for setting roles when adding users

        if action == "add" and group_id and user_id:
            user = get_object_or_404(User, id=user_id)
            group = get_object_or_404(Group, id=group_id)
            
            # Add the user to the group with the specified role
            UserGroups.objects.get_or_create(user=user, group=group, role=role)
        elif action == "remove" and group_id and user_id:
            user = get_object_or_404(User, id=user_id)
            group = get_object_or_404(Group, id=group_id)
            
            # Remove the user from the group
            UserGroups.objects.filter(user=user, group=group).delete()
    
    # Prepare context for rendering the template
    context = {
        'organization': organization,
        'groups': groups,
        'users_in_groups': users_in_groups,
        'users_not_in_groups': users_not_in_groups,
    }
    return render(request, 'editgroups.html', context)

@login_required
def update_user_group(request):
    try:
        # Try to handle both JSON and form data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                print("JSON decode error")
                return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
        else:
            data = request.POST

        user_id = data.get("user_id")
        action = data.get("action")
        group_id = data.get("group_id")

        # Validate user_id
        if not user_id:
            return JsonResponse({"success": False, "error": "User ID is required"}, status=400)
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return JsonResponse({"success": False, "error": "Invalid user ID"}, status=400)

        user = get_object_or_404(User, id=user_id)

        if action == "add":
            if not group_id:
                return JsonResponse({"success": False, "error": "Group ID is required"}, status=400)
            
            try:
                group_id = int(group_id)
            except (ValueError, TypeError):
                return JsonResponse({"success": False, "error": "Invalid group ID"}, status=400)
            
            group = get_object_or_404(Group, id=group_id)
            role = data.get("role", None)

            # First remove user from any existing groups in the same organization
            UserGroups.objects.filter(
                user=user,
                group__organization=group.organization
            ).delete()

            # Then add user to the new group
            UserGroups.objects.create(user=user, group=group, role=role)
            
            return JsonResponse({
                "success": True, 
                "message": f"{user.username} added to {group.name}"
            })

        elif action == "remove":
            if group_id:
                try:
                    group_id = int(group_id)
                except (ValueError, TypeError):
                    return JsonResponse({"success": False, "error": "Invalid group ID"}, status=400)
                
                # Remove from specific group
                deleted_count, _ = UserGroups.objects.filter(
                    user=user, 
                    group__id=group_id
                ).delete()
            else:
                # Remove from all groups
                deleted_count, _ = UserGroups.objects.filter(user=user).delete()

            if deleted_count:
                return JsonResponse({
                    "success": True, 
                    "message": "User removed successfully"
                })
            else:
                return JsonResponse({
                    "success": False, 
                    "error": "User not found in any group"
                }, status=404)

        return JsonResponse({"success": False, "error": "Invalid action"}, status=400)

    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({"error": str(e)}, status=500)



def update_group_name(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            group_name = data.get("groupName")
            group_id = data.get("groupId")

            if not group_id or not group_name:
                return JsonResponse({"success": False, "error": "Missing group ID or name"}, status=400)

            group = Group.objects.get(id=group_id)
            group.name = group_name
            group.save()

            return JsonResponse({"success": True, "message": "Group name updated successfully."})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request"}, status=400)


@login_required
@csrf_exempt
def add_user_to_group(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        group_id = request.POST.get("group_id")

        user = get_object_or_404(User, id=user_id)
        group = get_object_or_404(Group, id=group_id)

        # Add user to group
        UserGroups.objects.get_or_create(user=user, group=group)

        return JsonResponse({"success": True, "message": f"{user.username} added to {group.name}"})

@login_required
@csrf_exempt
def remove_user_from_group(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        group_id = request.POST.get("group_id")

        user = get_object_or_404(User, id=user_id)
        group = get_object_or_404(Group, id=group_id)

        # Remove user from group
        UserGroups.objects.filter(user=user, group=group).delete()

        return JsonResponse({"success": True, "message": f"{user.username} removed from {group.name}"})

@login_required
def delete_organization(request, org_id):
    # Get the organization or return a 404 if not found
    organization = get_object_or_404(Organization, id=org_id)

    # Ensure that the current user is the owner of the organization
    if organization.owner != request.user:
        raise Http404("You are not authorized to delete this organization.")

    # Delete the organization
    organization.delete()

    # Redirect to the home page or any other page after deletion
    messages.success(request, f"{organization.name} has been deleted.")
    return redirect('home')


@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id, owner=request.user)
    
    if request.method == 'POST':
        # Create a mutable copy of the POST data
        data = request.POST.copy()
        
        # Ensure required fields are present
        if not all(key in data for key in ['name', 'date', 'time', 'location', 'description', 'organization', 'latitude', 'longitude', 'radius']):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        # Create form with the data
        form = CreateEventForm(data, user=request.user, instance=event)
        
        if form.is_valid():
            event = form.save(commit=False)
            # Preserve the original organization and owner
            event.organization = Organization.objects.get(id=data['organization'])
            event.owner = request.user
            event.save()
            
            # Handle groups and update attendees
            new_groups = set(form.cleaned_data.get('groups', []))
            
            # Get all users from the new groups
            new_group_users = User.objects.filter(
                membership_groups__group__in=new_groups
            ).distinct()
            
            # Add all users from new groups as attendees
            for user in new_group_users:
                EventAttendees.objects.get_or_create(
                    event=event,
                    user=user
                )
            
            return JsonResponse({'success': True, 'message': 'Event updated successfully'})
        else:
            # Return form errors
            return JsonResponse({
                'success': False, 
                'error': 'Invalid form data',
                'form_errors': form.errors
            })
    else:
        form = CreateEventForm(user=request.user, instance=event)

    # Get all users from the event's organization
    org_users = User.objects.filter(
        user_organizations__organization=event.organization
    ).distinct()
    
    # Split users into attending and available
    attending_users = []
    available_users = []
    for user in org_users:
        is_attending = EventAttendees.objects.filter(event=event, user=user).exists()
        user_info = {
            'id': user.id,
            'name': f"{user.f_name} {user.l_name}",
            'is_attending': is_attending
        }
        if is_attending:
            attending_users.append(user_info)
        else:
            available_users.append(user_info)

    # Get all groups from the event's organization
    org_groups = Group.objects.filter(organization=event.organization)
    
    # Split groups into attending and available
    attending_groups = []
    available_groups = []
    for group in org_groups:
        is_attending = EventGroups.objects.filter(event=event, group=group).exists()
        group_info = {
            'id': group.id,
            'name': group.name,
            'is_attending': is_attending
        }
        if is_attending:
            attending_groups.append(group_info)
        else:
            available_groups.append(group_info)

    context = {
        'form': form,
        'event': event,
        'attending_users': attending_users,
        'available_users': available_users,
        'attending_groups': attending_groups,
        'available_groups': available_groups,
    }

    return render(request, 'editevent.html', context)


@login_required
def view_events(request):
    # Get organizations the user owns or is a member of
    organizations = Organization.objects.filter(
        Q(owner=request.user) | Q(user_organizations__user=request.user)
    ).distinct()
    
    # Get user's groups
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    
    # Base query for events
    events_query = Event.objects.filter(
        Q(attendees__user=request.user) |  # Events where user is an attendee
        Q(organization__in=organizations)  # Events from organizations user owns or is a member of
    ).distinct()
    
    # Apply organization filter if selected
    selected_organization_id = request.GET.get('organization_id')
    if selected_organization_id:
        events_query = events_query.filter(organization_id=selected_organization_id)
    
    # Get current time in UTC
    current_time = timezone.now()
    
    # Get all events and filter them in Python to handle timezone conversions properly
    all_events = events_query.order_by('date', 'time')
    upcoming_events = []
    
    for event in all_events:
        # Get the event's timezone
        event_tz = pytz.timezone(event.timezone)
        
        # Create a datetime object in the event's timezone
        event_datetime = timezone.datetime.combine(event.date, event.time)
        event_datetime = event_tz.localize(event_datetime)
        
        # Get current time in the event's timezone
        current_time_tz = current_time.astimezone(event_tz)
        
        # Calculate time difference
        time_until = event_datetime - current_time_tz
        minutes_until = int(time_until.total_seconds() / 60)
        
        # Only include events that haven't started yet or are within the check-in window
        if minutes_until > -5:  # Changed from > 0 to > -5 to include events in progress
            event.minutes_until = minutes_until
            # Set can_check_in property - allow check-in 30 minutes before and 5 minutes after event
            event.can_check_in = -5 <= minutes_until <= 30
            # Set is_concluded property - event is concluded if it's more than 5 minutes past start time
            event.is_concluded = minutes_until < -5
            # Check if user has already checked in
            event.user_check_in = EventCheckIn.objects.filter(
                user=request.user,
                event=event,
                is_within_radius=True
            ).exists()
            # Get attending groups for the event
            event.attending_groups = [{'name': event_group.group.name, 'color': event_group.group.color} for event_group in event.groups.all()]
            
            # Calculate time display
            if minutes_until >= 1440:  # More than 24 hours
                days = minutes_until // 1440
                remaining_minutes = minutes_until % 1440
                hours = remaining_minutes // 60
                event.time_display = f"{days}d {hours}h"
            elif minutes_until >= 60:  # More than 1 hour
                hours = minutes_until // 60
                minutes = minutes_until % 60
                event.time_display = f"{hours}h {minutes}m"
            else:
                event.time_display = f"{minutes_until}m"
            
            # Check if user is attending this event
            event.user_can_attend = EventAttendees.objects.filter(event=event, user=request.user).exists()
            
            upcoming_events.append(event)

    context = {
        'events': upcoming_events,
        'organizations': organizations,
        'selected_organization_id': selected_organization_id,
    }
    return render(request, 'viewevents.html', context)

@login_required
def view_past_events(request):
    # Get organizations the user owns or is a member of
    organizations = Organization.objects.filter(
        Q(owner=request.user) | Q(user_organizations__user=request.user)
    ).distinct()
    
    # Get user's groups
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    
    # Base query for events
    events_query = Event.objects.filter(
        Q(attendees__user=request.user) |  # Events where user is an attendee
        Q(organization__in=organizations)  # Events from organizations user owns or is a member of
    ).distinct()
    
    # Apply organization filter if selected
    selected_organization_id = request.GET.get('organization_id')
    if selected_organization_id:
        events_query = events_query.filter(organization_id=selected_organization_id)
    
    # Get current time in UTC
    current_time = timezone.now()
    
    # Get all events and filter them in Python to handle timezone conversions properly
    all_events = events_query.order_by('-date', '-time')
    past_events = []
    
    for event in all_events:
        # Get the event's timezone
        event_tz = pytz.timezone(event.timezone)
        
        # Create a datetime object in the event's timezone
        event_datetime = timezone.datetime.combine(event.date, event.time)
        event_datetime = event_tz.localize(event_datetime)
        
        # Get current time in the event's timezone
        current_time_tz = current_time.astimezone(event_tz)
        
        # Calculate time difference
        time_until = event_datetime - current_time_tz
        minutes_until = int(time_until.total_seconds() / 60)
        
        # Only include events that have already started
        if minutes_until <= 0:
            event.minutes_until = minutes_until
            # Get attending groups for the event
            event.attending_groups = [{'name': event_group.group.name, 'color': event_group.group.color} for event_group in event.groups.all()]
            # Check if user has already checked in
            event.user_check_in = EventCheckIn.objects.filter(
                user=request.user,
                event=event,
                is_within_radius=True
            ).exists()
            # Check if user is attending this event
            event.user_can_attend = EventAttendees.objects.filter(event=event, user=request.user).exists()
            past_events.append(event)

    context = {
        'events': past_events,
        'organizations': organizations,
        'selected_organization_id': selected_organization_id,
    }
    return render(request, 'pastevents.html', context)


@login_required
def view_organizations(request):
    # Get organizations owned by the user
    owned_organizations = get_owned_organizations(request)
    
    # Get organizations where user is a member
    member_organizations = Organization.objects.filter(
        user_organizations__user=request.user
    ).exclude(id__in=owned_organizations)
    
    context = {
        'owned_organizations': owned_organizations,
        'member_organizations': member_organizations,
    }
    
    return render(request, 'vieworgs.html', context)


@login_required
def create_org(request):
    if request.method == "POST":
        form = CreateOrganizationForm(data=request.POST)
        if form.is_valid():
            # Create the organization instance but don't save it yet
            organization = form.save(commit=False)
            organization.owner = request.user  # Set the current user as the owner
            organization.save()  # Save the organization to the database
            
            # Automatically add the user as a member of the organization
            UserOrganization.objects.create(user=request.user, organization=organization)
            
            # Check if this is the user's first organization
            owned_orgs_count = Organization.objects.filter(owner=request.user).count()
            
            # Optionally, add a success message
            messages.success(request, f"You've successfully created {organization.name} and joined it!")

            # If this is the user's first organization, redirect to create group page
            if owned_orgs_count == 1:
                return redirect('creategroup')
            return redirect('home')
    else:
        form = CreateOrganizationForm()

    context = {
        'form': form,
    }
    return render(request, 'createorg.html', context)



@login_required
def create_group(request):
    if request.method == "POST":
        form = CreateGroupForm(data=request.POST, user=request.user)
        if form.is_valid():
            group = form.save(commit=False)
            group.owner = request.user
            group.save()
        
            
            return redirect('home')
    else:
        form = CreateGroupForm(user=request.user)

    context = {
        'form':form,
    }
    return render(request, 'creategroup.html', context)

@login_required
def create_event(request):
    if request.method == 'POST':
        form = CreateEventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.owner = request.user
            # Store the creator's timezone
            event.timezone = request.POST.get('timezone', 'America/New_York')
            event.save()
            
            # Save the groups to EventGroups
            groups = form.cleaned_data.get('groups', [])
            for group in groups:
                EventGroups.objects.create(group=group, event=event)
            
            # Always add the organization owner as an attendee
            organization = form.cleaned_data.get('organization')
            if organization and organization.owner:
                EventAttendees.objects.get_or_create(
                    event=event,
                    user=organization.owner
                )
            
            # Handle groups and add their users as attendees
            for group in groups:
                # Add all users from the group as attendees
                group_users = UserGroups.objects.filter(group=group)
                for user_group in group_users:
                    EventAttendees.objects.get_or_create(
                        event=event,
                        user=user_group.user,
                        group=group  # Store the group reference
                    )
            
            messages.success(request, 'Event created successfully!')
            return redirect('viewevents')
    else:
        form = CreateEventForm(user=request.user)
    
    # Get user's timezone
    user_timezone = request.POST.get('timezone', 'America/New_York')
    
    context = {
        'form': form,
        'user_timezone': user_timezone,
    }
    return render(request, 'createevent.html', context)

@login_required
def get_groups_by_org(request, org_id):
    try:
        # Fetch groups for the specific organization
        groups = Group.objects.filter(organization_id=org_id).values('id', 'name')
        
        return JsonResponse({
            'groups': list(groups)
        })
    except Organization.DoesNotExist:
        return JsonResponse({'groups': []}, status=404)
    
@login_required
def join_org(request):
    if request.method == "POST":
        form = JoinOrganizationForm(request.POST)
        if form.is_valid():
            invite_code = form.cleaned_data['invite_code']
            organization = Organization.objects.get(invite_code=invite_code)
            
            # Ensure the user is not already a member
            if UserOrganization.objects.filter(user=request.user, organization=organization).exists():
                messages.warning(request, f"You are already a member of {organization.name}.")
            else:
                UserOrganization.objects.create(user=request.user, organization=organization)
                messages.success(request, f"Successfully joined {organization.name}!")

            return redirect("joinorg")  # Redirect to the same page or another page

    else:
        form = JoinOrganizationForm()

    return render(request, "joinorg.html", {"form": form})

@login_required
def update_event_group(request):
    try:
        data = json.loads(request.body)
        group_id = data.get('group_id')
        event_id = data.get('event_id')
        action = data.get('action')

        print(f"Received request to {action} group {group_id} to/from event {event_id}")

        if not all([group_id, event_id, action]):
            print("Missing required parameters:", {group_id, event_id, action})
            return JsonResponse({"success": False, "error": "Missing required parameters"}, status=400)

        # Get the event and verify ownership
        event = get_object_or_404(Event, id=event_id, owner=request.user)
        group = get_object_or_404(Group, id=group_id)

        print(f"Found event: {event.name} and group: {group.name}")

        if action == "add":
            # Add group to event
            event_group, created = EventGroups.objects.get_or_create(group=group, event=event)
            print(f"Added group to event. Created new: {created}")
            
            # Add all users from the group as attendees
            group_users = UserGroups.objects.filter(group=group)
            print(f"Found {group_users.count()} users in group")
            
            for user_group in group_users:
                attendee, created = EventAttendees.objects.get_or_create(
                    event=event,
                    user=user_group.user,
                    group=group
                )
                print(f"Added user {user_group.user.username} as attendee. Created new: {created}")

        elif action == "remove":
            # Remove group from event
            deleted_count = EventGroups.objects.filter(group=group, event=event).delete()
            print(f"Removed group from event. Deleted records: {deleted_count}")
            
            # Remove all users from this group as attendees
            deleted_attendees = EventAttendees.objects.filter(event=event, group=group).delete()
            print(f"Removed {deleted_attendees[0]} attendees from the event")

        return JsonResponse({"success": True})
    except Exception as e:
        print(f"Error in update_event_group: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
def delete_event(request, event_id):
    if request.method == 'POST':
        try:
            event = Event.objects.get(id=event_id)
            # Check if the user is the owner of the event
            if event.owner != request.user:
                return JsonResponse({'success': False, 'error': 'You do not have permission to delete this event'})
            
            event_name = event.name  # Store the event name before deletion
            event.delete()
            return JsonResponse({
                'success': True,
                'message': f'Event "{event_name}" has been successfully deleted.'
            })
        except Event.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Event not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@csrf_exempt
def update_user_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            
            if latitude is not None and longitude is not None:
                request.user.latitude = latitude
                request.user.longitude = longitude
                request.user.save()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Missing latitude or longitude'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

def calculate_distance(lat1, lon1, lat2, lon2):
    # Haversine formula to calculate distance between two points
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@login_required
@require_POST
def check_in_to_event(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
        
        # Handle both JSON and form data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                latitude = data.get('latitude')
                longitude = data.get('longitude')
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        else:
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')

        if not latitude or not longitude:
            return JsonResponse({'error': 'Location data is required'}, status=400)

        # Get the event's timezone
        event_tz = pytz.timezone(event.timezone)
        
        # Create a datetime object in the event's timezone
        event_datetime = timezone.datetime.combine(event.date, event.time)
        event_datetime = event_tz.localize(event_datetime)
        
        # Get current time in the event's timezone
        current_time = timezone.now().astimezone(event_tz)
        
        # Calculate time difference
        time_until = event_datetime - current_time
        minutes_until = int(time_until.total_seconds() / 60)
        
        # Check if within time window (-30 to 30 minutes around event time)
        is_within_time = -30 <= minutes_until <= 30

        # Calculate distance from event location
        distance = calculate_distance(
            event.geofence_latitude,
            event.geofence_longitude,
            latitude,
            longitude
        )

        # Check if within radius (convert radius to meters if needed)
        is_within_radius = distance <= event.geofence_radius

        # Only allow check-in if both conditions are met
        if not is_within_time:
            return JsonResponse({
                'error': 'Check-in is only available 30 minutes before and after the event time'
            }, status=400)
            
        if not is_within_radius:
            return JsonResponse({
                'error': 'You must be within the event location to check in',
                'distance': round(distance, 2),
                'radius': event.geofence_radius
            }, status=400)

        # Create or update check-in
        check_in, created = EventCheckIn.objects.update_or_create(
            user=request.user,
            event=event,
            defaults={
                'latitude': latitude,
                'longitude': longitude,
                'is_within_radius': is_within_radius,
                'check_in_time': timezone.now()
            }
        )

        # Also update EventAttendance
        attendance, _ = EventAttendance.objects.update_or_create(
            user=request.user,
            event=event,
            defaults={
                'check_in_time': timezone.now() if is_within_radius else None,
                'is_attending': is_within_radius
            }
        )

        return JsonResponse({
            'success': True,
            'is_within_radius': is_within_radius,
            'distance': round(distance, 2),
            'message': 'Check-in successful'
        })

    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def event_attendance(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Only event owners can view attendance
    if event.owner != request.user:
        messages.error(request, "You don't have permission to view this event's attendance.")
        return redirect('home')
    
    # Get all users who are expected to attend through EventAttendees
    individual_attendees = User.objects.filter(
        attending_events__event=event
    ).exclude(id=event.owner.id).distinct()
    
    # Get all users who are expected to attend through their group membership
    group_attendees = User.objects.filter(
        membership_groups__group__in=EventGroups.objects.filter(event=event).values('group')
    ).exclude(id=event.owner.id).distinct()
    
    # Combine both sets of expected attendees
    expected_attendees = (individual_attendees | group_attendees).distinct()
    
    # Get all check-ins for this event
    check_ins = EventCheckIn.objects.filter(
        event=event,
        is_within_radius=True
    ).select_related('user').exclude(user=event.owner)  # Exclude the event owner
    
    # Create attendance lists
    attended = [check_in.user for check_in in check_ins]
    
    # Get all users who checked in but weren't expected to attend
    unexpected_attendees = [user for user in attended if user not in expected_attendees]
    
    # Get all expected attendees who didn't show up
    absent = [user for user in expected_attendees if user not in attended]
    
    # Calculate attendance rate safely
    total_expected = len(expected_attendees)
    total_attended = len(attended)
    attendance_rate = (total_attended / total_expected * 100) if total_expected > 0 else 0
    
    context = {
        'event': event,
        'attended': attended,
        'absent': absent,
        'unexpected_attendees': unexpected_attendees,
        'total_expected': total_expected,
        'total_attended': total_attended,
        'attendance_rate': attendance_rate
    }
    
    return render(request, 'event_attendance.html', context)

@login_required
def account_details(request):
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        
        # Update user details
        user = request.user
        user.f_name = first_name
        user.l_name = last_name
        user.email = email
        user.username = username
        
        try:
            user.save()
            messages.success(request, 'Account details updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating account details: {str(e)}')
        
        return redirect('account_details')
    
    return render(request, 'account_details.html', {
        'user': request.user,
    })

@login_required
def notifications(request):
    return render(request, 'notifications.html', {
        'user': request.user,
    })

@login_required
def settings(request):
    return render(request, 'settings.html', {
        'user': request.user,
    })

@login_required
def help_support(request):
    return render(request, 'help.html', {
        'user': request.user,
    })

@login_required
def get_substitution_requests(request):
    if request.method == 'GET':
        event_id = request.GET.get('event_id')
        
        try:
            event = Event.objects.get(id=event_id)
            
            # Get requests where user is either requesting or target
            requests = SubstitutionRequest.objects.filter(
                event=event
            ).filter(
                Q(requesting_user=request.user) | Q(target_user=request.user)
            ).order_by('-created_at')
            
            requests_data = [{
                'id': req.id,
                'requesting_user': {
                    'id': req.requesting_user.id,
                    'name': f"{req.requesting_user.f_name} {req.requesting_user.l_name}",
                    'username': req.requesting_user.username
                },
                'target_user': {
                    'id': req.target_user.id,
                    'name': f"{req.target_user.f_name} {req.target_user.l_name}",
                    'username': req.target_user.username
                },
                'status': req.status,
                'created_at': req.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for req in requests]
            
            return JsonResponse({'success': True, 'requests': requests_data})
        except Event.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Event not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def request_substitution(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event_id = data.get('event_id')
            target_user_id = data.get('target_user_id')
            
            if not event_id or not target_user_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                })
            
            event = Event.objects.get(id=event_id)
            target_user = User.objects.get(id=target_user_id)
            
            # Check if requesting user is a member of the event's organization
            if not UserOrganization.objects.filter(user=request.user, organization=event.organization).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'You are not a member of this organization'
                })
            
            # Check if target user is a member of the event's organization
            if not UserOrganization.objects.filter(user=target_user, organization=event.organization).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Target user is not a member of this organization'
                })
            
            # Check if users have matching tags
            if request.user.tag and target_user.tag:
                if request.user.tag != target_user.tag:
                    return JsonResponse({
                        'success': False,
                        'error': 'You can only request substitutions from users with the same tag'
                    })
            
            # Check if there's already a pending request
            existing_request = SubstitutionRequest.objects.filter(
                event=event,
                requesting_user=request.user,
                target_user=target_user,
                status='pending'
            ).exists()
            
            if existing_request:
                return JsonResponse({
                    'success': False,
                    'error': 'You already have a pending substitution request for this event'
                })
            
            # Create the substitution request
            SubstitutionRequest.objects.create(
                event=event,
                requesting_user=request.user,
                target_user=target_user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Substitution request created successfully'
            })
            
        except Event.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Event not found'
            })
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Target user not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)

@login_required
def view_announcements(request):
    # Get organizations where user is either owner or member
    owned_organizations = Organization.objects.filter(owner=request.user)
    member_organizations = Organization.objects.filter(
        user_organizations__user=request.user
    ).exclude(owner=request.user)

    # Combine both querysets
    organizations = list(owned_organizations) + list(member_organizations)

    # Get all announcements from all organizations the user has access to
    announcements = Announcement.objects.filter(
        organization__in=organizations,
        is_active=True
    ).select_related('created_by', 'organization').prefetch_related('files').order_by('-created_at')

    context = {
        'organizations': organizations,  # Keep this for the create announcement dropdown
        'announcements': announcements,
    }
    return render(request, 'viewannouncements.html', context)

@login_required
@require_POST
def edit_announcement(request, announcement_id):
    try:
        # Get the announcement and verify ownership
        announcement = get_object_or_404(Announcement, id=announcement_id)
        if announcement.organization.owner != request.user:
            return JsonResponse({'error': 'You do not have permission to edit this announcement'}, status=403)

        # Get data from request
        data = request.POST
        files = request.FILES.getlist('files')
        files_to_remove = request.POST.getlist('files_to_remove')

        # Update announcement details
        announcement.title = data.get('title')
        announcement.content = data.get('content')
        announcement.save()

        # Remove selected files
        if files_to_remove:
            AnnouncementFile.objects.filter(id__in=files_to_remove).delete()

        # Add new files
        for file in files:
            AnnouncementFile.objects.create(
                announcement=announcement,
                file=file,
                filename=file.name
            )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_announcement_files(request, announcement_id):
    try:
        # Get the announcement and verify access
        announcement = get_object_or_404(Announcement, id=announcement_id)
        if not (announcement.organization.owner == request.user or 
                UserOrganization.objects.filter(user=request.user, organization=announcement.organization).exists()):
            return JsonResponse({'error': 'You do not have permission to view these files'}, status=403)

        # Get files
        files = announcement.files.all()
        files_data = [{
            'id': file.id,
            'filename': file.filename,
            'url': file.file.url
        } for file in files]

        return JsonResponse({'files': files_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_announcement_details(request, announcement_id):
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        # Check if user has access to this announcement
        if not (announcement.organization.owner == request.user or request.user in announcement.organization.members.all()):
            return JsonResponse({'error': 'You do not have permission to access this announcement'}, status=403)
        
        return JsonResponse({
            'title': announcement.title,
            'content': announcement.content,
            'organization_id': announcement.organization.id
        })
    except Announcement.DoesNotExist:
        return JsonResponse({'error': 'Announcement not found'}, status=404)

@login_required
def update_group_color(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            group_id = data.get('groupId')
            color = data.get('color')
            
            if not group_id or not color:
                return JsonResponse({'success': False, 'error': 'Missing required fields'})
            
            group = Group.objects.get(id=group_id)
            
            # Verify user has permission to edit this group
            if group.organization.owner != request.user:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
            
            group.color = color
            group.save()
            
            return JsonResponse({'success': True})
        except Group.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Group not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def update_event_attendee(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            event_id = data.get('event_id')
            action = data.get('action')

            print(f"Received request to {action} user {user_id} to/from event {event_id}")

            if not all([user_id, event_id, action]):
                print("Missing required parameters:", {user_id, event_id, action})
                return JsonResponse({'success': False, 'error': 'Missing required fields'})

            event = Event.objects.get(id=event_id)
            user = User.objects.get(id=user_id)

            # Verify the current user has permission to modify the event
            if not (request.user.is_staff or event.owner == request.user):
                return JsonResponse({'success': False, 'error': 'Permission denied'})

            # Check for pending substitution requests
            pending_requests = SubstitutionRequest.objects.filter(
                event=event,
                status='pending'
            ).filter(
                Q(requesting_user=user) | Q(target_user=user)
            )

            if pending_requests.exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Cannot modify attendance while there are pending substitution requests for this user'
                })

            # Check for existing substitutions
            existing_substitution = EventSubstitution.objects.filter(
                event=event
            ).filter(
                Q(original_user=user) | Q(substitute_user=user)
            ).first()

            if existing_substitution:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot modify attendance for users involved in a substitution'
                })

            if action == 'add':
                # Get the user's group in this event's organization
                user_group = UserGroups.objects.filter(
                    user=user,
                    group__organization=event.organization
                ).first()
                
                # Add user as attendee with their group
                EventAttendees.objects.get_or_create(
                    event=event,
                    user=user,
                    group=user_group.group if user_group else None
                )
                print(f"Added user {user.username} as attendee")
            elif action == 'remove':
                # Remove from EventAttendees
                deleted_count = EventAttendees.objects.filter(event=event, user=user).delete()
                print(f"Removed {deleted_count[0]} attendee records")
                
                # Also remove any check-ins or attendance records
                EventCheckIn.objects.filter(event=event, user=user).delete()
                EventAttendance.objects.filter(event=event, user=user).delete()
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})

            return JsonResponse({'success': True})
        except (Event.DoesNotExist, User.DoesNotExist):
            print(f"Event or user not found: Event ID {event_id}, User ID {user_id}")
            return JsonResponse({'success': False, 'error': 'Event or user not found'})
        except Exception as e:
            print(f"Error in update_event_attendee: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def get_group_members(request, group_id):
    try:
        group = Group.objects.get(id=group_id)
        members = group.members.all()
        return JsonResponse({
            'success': True,
            'members': [{
                'id': member.id,
                'name': member.get_full_name() or member.username
            } for member in members]
        })
    except Group.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Group not found'
        }, status=404)

@login_required
def add_substitution(request):
    if not request.user.is_staff:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    try:
        event = Event.objects.get(id=request.POST.get('event_id'))
        group = Group.objects.get(id=request.POST.get('group'))
        original_user = User.objects.get(id=request.POST.get('original_user'))
        substitute_user = User.objects.get(id=request.POST.get('substitute_user'))

        # Check if original user is in the group
        if not group.members.filter(id=original_user.id).exists():
            return JsonResponse({
                'success': False,
                'error': 'Original user is not a member of the selected group'
            }, status=400)

        # Check if substitute user is in the group
        if not group.members.filter(id=substitute_user.id).exists():
            return JsonResponse({
                'success': False,
                'error': 'Substitute user is not a member of the selected group'
            }, status=400)

        # Check if substitution already exists
        if EventSubstitution.objects.filter(
            event=event,
            original_user=original_user,
            group=group
        ).exists():
            return JsonResponse({
                'success': False,
                'error': 'A substitution already exists for this user in this group'
            }, status=400)

        # Create the substitution
        substitution = EventSubstitution.objects.create(
            event=event,
            original_user=original_user,
            substitute_user=substitute_user,
            group=group,
            created_by=request.user
        )

        return JsonResponse({
            'success': True,
            'message': 'Substitution added successfully'
        })

    except (Event.DoesNotExist, Group.DoesNotExist, User.DoesNotExist):
        return JsonResponse({
            'success': False,
            'error': 'Invalid event, group, or user'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def remove_substitution(request, substitution_id):
    if not request.user.is_staff:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    try:
        substitution = EventSubstitution.objects.get(id=substitution_id)
        substitution.delete()
        return JsonResponse({
            'success': True,
            'message': 'Substitution removed successfully'
        })
    except EventSubstitution.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Substitution not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def view_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is in any of the groups attending the event
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    event_groups = EventGroups.objects.filter(event=event).values_list('group', flat=True)
    user_can_attend = any(group in event_groups for group in user_groups)
    
    if not user_can_attend and event.owner != request.user:
        messages.error(request, "You are not authorized to view this event.")
        return redirect('home')
    
    # Get the event's timezone
    event_tz = pytz.timezone(event.timezone)
    
    # Create a datetime object in the event's timezone
    event_datetime = timezone.datetime.combine(event.date, event.time)
    event_datetime = event_tz.localize(event_datetime)
    
    # Get current time in the event's timezone
    current_time = timezone.now().astimezone(event_tz)
    
    # Calculate time difference
    time_until = event_datetime - current_time
    minutes_until = int(time_until.total_seconds() / 60)
    
    # Set event properties
    event.minutes_until = minutes_until
    event.can_check_in = -5 <= minutes_until <= 30
    event.is_concluded = minutes_until < -5
    event.user_check_in = EventCheckIn.objects.filter(
        event=event,
        user=request.user,
        is_within_radius=True
    ).exists()
    
    # Get attending groups for the event
    event.attending_groups = []
    for event_group in event.groups.all():
        # Get members through membership_groups relationship
        members = User.objects.filter(membership_groups__group=event_group.group)
        event.attending_groups.append({
            'id': event_group.group.id,
            'name': event_group.group.name,
            'color': event_group.group.color,
            'members': members,
            'member_count': members.count()
        })
    
    # Calculate time display
    if minutes_until >= 1440:  # More than 24 hours
        days = minutes_until // 1440
        remaining_minutes = minutes_until % 1440
        hours = remaining_minutes // 60
        event.time_display = f"{days}d {hours}h"
    elif minutes_until >= 60:  # More than 1 hour
        hours = minutes_until // 60
        minutes = minutes_until % 60
        event.time_display = f"{hours}h {minutes}m"
    else:
        event.time_display = f"{minutes_until}m"
    
    # Get substitutions for the event
    substitutions = EventSubstitution.objects.filter(event=event).select_related(
        'original_user', 'substitute_user', 'group'
    )
    
    # Get substitution requests for the event
    substitution_requests = SubstitutionRequest.objects.filter(event=event).select_related(
        'requesting_user', 'target_user', 'group'
    )
    
    context = {
        'event': event,
        'user_can_attend': user_can_attend,
        'substitutions': substitutions,
        'substitution_requests': substitution_requests,
        'user': request.user,
    }
    
    return render(request, 'viewevent.html', context)

@login_required
def event_checkin_page(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is in any of the groups attending the event
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    event_groups = EventGroups.objects.filter(event=event).values_list('group', flat=True)
    user_can_attend = any(group in event_groups for group in user_groups)
    
    if not user_can_attend and event.owner != request.user:
        messages.error(request, "You are not authorized to view this event.")
        return redirect('home')
    
    # Get the event's timezone
    event_tz = pytz.timezone(event.timezone)
    
    # Create a datetime object in the event's timezone
    event_datetime = timezone.datetime.combine(event.date, event.time)
    event_datetime = event_tz.localize(event_datetime)
    
    # Get current time in the event's timezone
    current_time = timezone.now().astimezone(event_tz)
    
    # Calculate time difference
    time_until = event_datetime - current_time
    minutes_until = int(time_until.total_seconds() / 60)
    
    # Set event properties
    event.minutes_until = minutes_until
    event.can_check_in = -5 <= minutes_until <= 30
    event.is_concluded = minutes_until < -5
    event.user_check_in = EventCheckIn.objects.filter(
        event=event,
        user=request.user,
        is_within_radius=True
    ).exists()
    
    # Get attending groups for the event
    event.attending_groups = []
    for event_group in event.groups.all():
        # Get members through membership_groups relationship
        members = User.objects.filter(membership_groups__group=event_group.group)
        event.attending_groups.append({
            'id': event_group.group.id,
            'name': event_group.group.name,
            'color': event_group.group.color,
            'members': members,
            'member_count': members.count()
        })
    
    # Calculate time display
    if minutes_until >= 1440:  # More than 24 hours
        days = minutes_until // 1440
        remaining_minutes = minutes_until % 1440
        hours = remaining_minutes // 60
        event.time_display = f"{days}d {hours}h"
    elif minutes_until >= 60:  # More than 1 hour
        hours = minutes_until // 60
        minutes = minutes_until % 60
        event.time_display = f"{hours}h {minutes}m"
    else:
        event.time_display = f"{minutes_until}m"
    
    context = {
        'event': event,
        'user_can_attend': user_can_attend,
        'user': request.user,
    }
    
    return render(request, 'event_checkin.html', context)

@login_required
def create_announcement(request, org_id):
    if request.method == 'POST':
        try:
            organization = get_object_or_404(Organization, id=org_id)
            
            # Verify user has permission to create announcements
            if organization.owner != request.user:
                return JsonResponse({'error': 'You do not have permission to create announcements'}, status=403)
            
            # Get data from request
            title = request.POST.get('title')
            content = request.POST.get('content')
            files = request.FILES.getlist('files')
            
            if not title or not content:
                return JsonResponse({'error': 'Title and content are required'}, status=400)
            
            # Create the announcement
            announcement = Announcement.objects.create(
                organization=organization,
                title=title,
                content=content,
                created_by=request.user
            )
            
            # Handle file attachments
            for file in files:
                AnnouncementFile.objects.create(
                    announcement=announcement,
                    file=file,
                    filename=file.name
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Announcement created successfully',
                'announcement_id': announcement.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def get_announcements(request, org_id):
    try:
        organization = get_object_or_404(Organization, id=org_id)
        
        # Get announcements for the organization
        announcements = Announcement.objects.filter(
            organization=organization,
            is_active=True
        ).select_related('created_by').prefetch_related('files').order_by('-created_at')
        
        announcements_data = [{
            'id': announcement.id,
            'title': announcement.title,
            'content': announcement.content,
            'created_at': announcement.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': announcement.created_by.get_full_name() or announcement.created_by.username,
            'files': [{
                'id': file.id,
                'filename': file.filename,
                'url': file.file.url
            } for file in announcement.files.all()]
        } for announcement in announcements]
        
        return JsonResponse({
            'success': True,
            'announcements': announcements_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def delete_announcement(request, announcement_id):
    if request.method == 'POST':
        try:
            announcement = get_object_or_404(Announcement, id=announcement_id)
            
            # Verify user has permission to delete
            if announcement.organization.owner != request.user:
                return JsonResponse({'error': 'You do not have permission to delete this announcement'}, status=403)
            
            # Soft delete by setting is_active to False
            announcement.is_active = False
            announcement.save()
            
            return JsonResponse({'success': True, 'message': 'Announcement deleted successfully'})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def pending_substitution_requests(request):
    try:
        # Get all pending substitution requests for the current user
        pending_requests = SubstitutionRequest.objects.filter(
            target_user=request.user,
            status='pending'
        ).select_related(
            'event',
            'requesting_user',
            'target_user'
        ).order_by('-created_at')
        
        # Add event timezone info to each request
        for sub_request in pending_requests:
            try:
                event_tz = pytz.timezone(sub_request.event.timezone)
                event_datetime = timezone.datetime.combine(sub_request.event.date, sub_request.event.time)
                event_datetime = event_tz.localize(event_datetime)
                sub_request.event_datetime = event_datetime
            except Exception as e:
                print(f"Error processing timezone for request {sub_request.id}: {str(e)}")
                sub_request.event_datetime = None
        
        context = {
            'pending_requests': pending_requests,
            'total_pending': pending_requests.count()
        }
        
        return render(request, 'pending_substitution_requests.html', context)
        
    except Exception as e:
        print(f"Error in pending_substitution_requests: {str(e)}")
        messages.error(request, 'Error loading pending substitution requests')
        return redirect('home')

@login_required
def get_user_group(request, event_id):
    try:
        event = get_object_or_404(Event, id=event_id)
        attendee = EventAttendees.objects.get(event=event, user=request.user)
        
        if not attendee.group:
            return JsonResponse({
                'success': False,
                'error': 'No group found for your attendance'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'group': {
                'id': attendee.group.id,
                'name': attendee.group.name,
                'color': attendee.group.color
            }
        })
    except EventAttendees.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'You are not attending this event'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def request_sub(request, event_id):
    try:
        event = get_object_or_404(Event, id=event_id)
        
        # Check if user is authorized to request substitution
        user_can_attend = EventAttendees.objects.filter(event=event, user=request.user).exists()
        
        if not user_can_attend and event.owner != request.user:
            messages.error(request, "You are not authorized to view this event.")
            return redirect('home')
        
        # Get all users from the organization who aren't currently attending
        organization_users = User.objects.filter(
            user_organizations__organization=event.organization
        ).exclude(
            # Exclude users who are already attending
            id__in=EventAttendees.objects.filter(event=event).values_list('user_id', flat=True)
        ).exclude(
            # Exclude the event owner
            id=event.organization.owner.id
        ).distinct()
        
        # If the current user has a tag, filter potential substitutes to only show users with the same tag
        if request.user.tag:
            organization_users = organization_users.filter(tag=request.user.tag)
        
        # Get pending requests count for the current user
        pending_requests_count = SubstitutionRequest.objects.filter(
            event=event,
            target_user=request.user,
            status='pending'
        ).count()
        
        # Get the event's timezone
        event_tz = pytz.timezone(event.timezone)
        
        # Create a datetime object in the event's timezone
        event_datetime = timezone.datetime.combine(event.date, event.time)
        event_datetime = event_tz.localize(event_datetime)
        
        # Get current time in the event's timezone
        current_time = timezone.now().astimezone(event_tz)
        
        # Calculate time difference
        time_until = event_datetime - current_time
        minutes_until = int(time_until.total_seconds() / 60)
        
        # Set event properties
        event.minutes_until = minutes_until
        event.can_check_in = -5 <= minutes_until <= 30
        event.is_concluded = minutes_until < -5
        event.user_check_in = EventCheckIn.objects.filter(
            event=event,
            user=request.user,
            is_within_radius=True
        ).exists()
        
        # Get attending groups for the event
        event.attending_groups = []
        for event_group in event.groups.all():
            # Get members through membership_groups relationship
            members = User.objects.filter(membership_groups__group=event_group.group)
            event.attending_groups.append({
                'id': event_group.group.id,
                'name': event_group.group.name,
                'color': event_group.group.color,
                'members': members,
                'member_count': members.count()
            })
        
        # Calculate time display
        if minutes_until >= 1440:  # More than 24 hours
            days = minutes_until // 1440
            remaining_minutes = minutes_until % 1440
            hours = remaining_minutes // 60
            event.time_display = f"{days}d {hours}h"
        elif minutes_until >= 60:  # More than 1 hour
            hours = minutes_until // 60
            minutes = minutes_until % 60
            event.time_display = f"{hours}h {minutes}m"
        else:
            event.time_display = f"{minutes_until}m"
        
        # Get substitutions for the event
        substitutions = EventSubstitution.objects.filter(event=event).select_related(
            'original_user', 'substitute_user', 'created_by'
        )
        
        # Get substitution requests for the event
        substitution_requests = SubstitutionRequest.objects.filter(event=event).select_related(
            'requesting_user', 'target_user'
        )
        
        context = {
            'event': event,
            'user_can_attend': user_can_attend,
            'substitutions': substitutions,
            'substitution_requests': substitution_requests,
            'user': request.user,
            'organization_users': organization_users,
            'pending_requests_count': pending_requests_count,
        }
        
        return render(request, 'requestsub.html', context)
        
    except Exception as e:
        print(f"Error in request_sub: {str(e)}")
        messages.error(request, 'Error loading substitution page')
        return redirect('home')

@login_required
def respond_to_substitution_request(request, request_id):
    if request.method == 'POST':
        try:
            sub_request = get_object_or_404(SubstitutionRequest, id=request_id, target_user=request.user)
            action = request.POST.get('action')
            
            if action == 'accept':
                try:
                    # Create substitution record
                    EventSubstitution.objects.create(
                        event=sub_request.event,
                        original_user=sub_request.requesting_user,
                        substitute_user=sub_request.target_user,
                        created_by=sub_request.requesting_user
                    )
                    
                    # Update request status
                    sub_request.status = 'accepted'
                    sub_request.save()
                    
                    # Remove the requesting user from attendees
                    EventAttendees.objects.filter(
                        event=sub_request.event,
                        user=sub_request.requesting_user
                    ).delete()
                    
                    # Add the target user (accepter) to attendees
                    EventAttendees.objects.create(
                        event=sub_request.event,
                        user=sub_request.target_user
                    )
                    
                    # Clean up check-ins and attendance records for both users
                    EventCheckIn.objects.filter(
                        event=sub_request.event,
                        user__in=[sub_request.requesting_user, sub_request.target_user]
                    ).delete()
                    
                    EventAttendance.objects.filter(
                        event=sub_request.event,
                        user__in=[sub_request.requesting_user, sub_request.target_user]
                    ).delete()
                    
                    # Create new attendance record for the substitute user (accepter)
                    EventAttendance.objects.create(
                        event=sub_request.event,
                        user=sub_request.target_user,
                        is_attending=True
                    )
                    
                    return JsonResponse({'success': True})
                    
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'error': f'Error accepting substitution request: {str(e)}'
                    }, status=500)
                    
            elif action == 'reject':
                sub_request.status = 'rejected'
                sub_request.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action'
                }, status=400)
                
        except SubstitutionRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Substitution request not found'
            }, status=404)
            
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)

@login_required
def manage_tags(request, org_id):
    # Get the organization or raise a 404 if not found
    organization = get_object_or_404(Organization, id=org_id)
    
    # Check if user is the owner of the organization
    if request.user != organization.owner:
        return HttpResponseForbidden("You don't have permission to manage tags for this organization.")
    
    # Get all tags for this organization
    tags = Tag.objects.filter(organization=organization)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = request.POST.get('name')
            color = request.POST.get('color', '#6666ff')
            
            if name:
                Tag.objects.create(
                    name=name,
                    organization=organization,
                    created_by=request.user,
                    color=color
                )
                messages.success(request, f'Tag "{name}" created successfully.')
            else:
                messages.error(request, 'Tag name is required.')
                
        elif action == 'delete':
            tag_id = request.POST.get('tag_id')
            try:
                tag = Tag.objects.get(id=tag_id, organization=organization)
                tag.delete()
                messages.success(request, f'Tag "{tag.name}" deleted successfully.')
            except Tag.DoesNotExist:
                messages.error(request, 'Tag not found.')
                
        elif action == 'update':
            tag_id = request.POST.get('tag_id')
            name = request.POST.get('name')
            color = request.POST.get('color')
            
            try:
                tag = Tag.objects.get(id=tag_id, organization=organization)
                if name:
                    tag.name = name
                if color:
                    tag.color = color
                tag.save()
                messages.success(request, f'Tag updated successfully.')
            except Tag.DoesNotExist:
                messages.error(request, 'Tag not found.')
                
        return redirect('manage_tags', org_id=org_id)
    
    context = {
        'organization': organization,
        'tags': tags,
    }
    return render(request, 'managetags.html', context)

@login_required
def update_user_tag(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            tag_id = data.get('tag_id')
            
            print(f"Received request to update tag - User ID: {user_id}, Tag ID: {tag_id}")
            
            if not user_id:
                return JsonResponse({'success': False, 'error': 'User ID is required.'})
            
            # Get the target user
            target_user = User.objects.get(id=user_id)
            print(f"Found target user: {target_user.username}")
            
            # Get the organization from the tag if provided
            organization = None
            if tag_id:
                tag = Tag.objects.get(id=tag_id)
                organization = tag.organization
                print(f"Found tag: {tag.name} in organization: {organization.name}")
            else:
                # If removing tag, get organization from user's current tag
                if target_user.tag:
                    organization = target_user.tag.organization
                    print(f"Found organization from current tag: {organization.name}")
            
            if not organization:
                print("No organization found")
                return JsonResponse({'success': False, 'error': 'Organization not found.'})
            
            # Check if the requesting user is the organization owner
            if organization.owner != request.user:
                print(f"Permission denied - Requesting user {request.user.username} is not owner of {organization.name}")
                return JsonResponse({'success': False, 'error': 'Only organization owners can update tags.'})
            
            # Update the target user's tag
            if tag_id:
                target_user.tag = tag
                print(f"Setting tag {tag.name} for user {target_user.username}")
            else:
                target_user.tag = None
                print(f"Removing tag for user {target_user.username}")
            
            target_user.save()
            print(f"Successfully saved user {target_user.username} with tag {target_user.tag.name if target_user.tag else 'None'}")
            
            return JsonResponse({'success': True})
                
        except User.DoesNotExist:
            print(f"User not found with ID: {user_id}")
            return JsonResponse({'success': False, 'error': 'User not found.'})
        except Tag.DoesNotExist:
            print(f"Tag not found with ID: {tag_id}")
            return JsonResponse({'success': False, 'error': 'Tag not found.'})
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@login_required
def get_organization_tags(request, org_id):
    try:
        organization = Organization.objects.get(id=org_id)
        # Check if user is a member of the organization
        if not UserOrganization.objects.filter(user=request.user, organization=organization).exists():
            return JsonResponse({'success': False, 'error': 'You are not a member of this organization.'})
        
        tags = Tag.objects.filter(organization=organization).values('id', 'name', 'color')
        return JsonResponse({'success': True, 'tags': list(tags)})
    except Organization.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Organization not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def event_details(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
        
        # Get all substitution requests for this event
        substitution_requests = SubstitutionRequest.objects.filter(event=event)
        
        # Get potential substitutes (users in the same organization who are not already attendees)
        potential_substitutes = User.objects.filter(
            userorganization__organization=event.organization
        ).exclude(
            id__in=event.attendees.values_list('user_id', flat=True)
        )
        
        # If the current user has a tag, filter potential substitutes to only show users with the same tag
        if request.user.tag:
            potential_substitutes = potential_substitutes.filter(tag=request.user.tag)
        
        context = {
            'event': event,
            'substitution_requests': substitution_requests,
            'potential_substitutes': potential_substitutes,
        }
        
        return render(request, 'event_details.html', context)
        
    except Event.DoesNotExist:
        messages.error(request, 'Event not found')
        return redirect('home')

def get_owned_organizations(request):
    """Helper function to get organizations owned by the user"""
    return Organization.objects.filter(owner=request.user)

@login_required
def get_event_attendees(request, event_id):
    try:
        event = get_object_or_404(Event, id=event_id)
        
        # Get all users from the event's organization
        org_users = User.objects.filter(
            user_organizations__organization=event.organization
        ).distinct()
        
        # Split users into attending and available
        attending_users = []
        available_users = []
        
        for user in org_users:
            is_attending = EventAttendees.objects.filter(event=event, user=user).exists()
            user_info = {
                'id': user.id,
                'name': f"{user.f_name} {user.l_name}",
                'is_attending': is_attending
            }
            if is_attending:
                attending_users.append(user_info)
            else:
                available_users.append(user_info)
        
        return JsonResponse({
            'success': True,
            'attending_users': attending_users,
            'available_users': available_users
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_POST
def update_org_name(request, org_id):
    try:
        # Get the organization
        org = Organization.objects.get(id=org_id)
        
        # Check if user is the owner
        if org.owner != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to edit this organization'
            })
        
        # Get the new name from request body
        data = json.loads(request.body)
        new_name = data.get('name', '').strip()
        
        if not new_name:
            return JsonResponse({
                'success': False,
                'error': 'Organization name cannot be empty'
            })
        
        # Update the name
        org.name = new_name
        org.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Organization name updated successfully'
        })
        
    except Organization.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Organization not found'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def org_attendance(request):
    # Get all organizations the user is a member of
    organizations = Organization.objects.filter(user_organizations__user=request.user)
    return render(request, 'org_attendance.html', {'organizations': organizations})

@login_required
def get_org_attendance(request, org_id):
    try:
        org = Organization.objects.get(id=org_id, user_organizations__user=request.user)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organization not found'}, status=404)

    # Get filter parameter
    filter_type = request.GET.get('filter', 'all')
    
    # Calculate date range based on filter
    now = timezone.now()
    if filter_type == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif filter_type == 'quarter':
        current_quarter = (now.month - 1) // 3 + 1
        start_date = now.replace(month=3 * current_quarter - 2, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif filter_type == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # all
        start_date = None

    # Get all events for the organization
    events = Event.objects.filter(organization=org)
    if start_date:
        events = events.filter(date__gte=start_date)
    
    total_events = events.count()
    
    # Get attendance data for each member
    attendance_data = []
    for user_org in org.user_organizations.all():
        member = user_org.user
        # Get events where the member has attendance records
        member_events = Event.objects.filter(
            organization=org,
            attendance__user=member,
            attendance__is_attending=True
        )
        if start_date:
            member_events = member_events.filter(date__gte=start_date)
        
        attended_count = member_events.count()
        
        # Calculate attendance rate
        attendance_rate = round((attended_count / total_events * 100) if total_events > 0 else 0)
        
        # Get last attended date
        last_attended = member_events.order_by('-date').first()
        last_attended_date = last_attended.date.strftime('%m/%d/%Y') if last_attended else 'Never'
        
        # Get tag information
        tag_name = member.tag.name if member.tag else None
        tag_color = member.tag.color if member.tag else None
        
        attendance_data.append({
            'id': member.id,
            'name': f"{member.f_name} {member.l_name}",
            'total_events': total_events,
            'attended_events': attended_count,
            'attendance_rate': attendance_rate,
            'last_attended': last_attended_date,
            'tag_name': tag_name,
            'tag_color': tag_color
        })
    
    return JsonResponse(attendance_data, safe=False)

@login_required
def export_org_attendance(request, org_id):
    try:
        org = Organization.objects.get(id=org_id, user_organizations__user=request.user)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organization not found'}, status=404)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{org.name}_attendance.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Member Name', 'Total Events', 'Attended Events', 'Attendance Rate', 'Last Attended'])
    
    # Get all events for the organization
    events = Event.objects.filter(organization=org)
    total_events = events.count()
    
    # Write attendance data for each member
    for user_org in org.user_organizations.all():
        member = user_org.user
        # Get events where the member has attendance records
        member_events = Event.objects.filter(
            organization=org,
            attendance__user=member,
            attendance__is_attending=True
        )
        attended_count = member_events.count()
        attendance_rate = round((attended_count / total_events * 100) if total_events > 0 else 0)
        
        last_attended = member_events.order_by('-date').first()
        last_attended_date = last_attended.date.strftime('%m/%d/%Y') if last_attended else 'Never'
        
        writer.writerow([
            f"{member.f_name} {member.l_name}",
            total_events,
            attended_count,
            f"{attendance_rate}%",
            last_attended_date
        ])
    
    return response

@login_required
def get_member_attendance_details(request, org_id, member_id):
    try:
        org = Organization.objects.get(id=org_id, user_organizations__user=request.user)
        member = User.objects.get(id=member_id)
    except (Organization.DoesNotExist, User.DoesNotExist):
        return JsonResponse({'error': 'Organization or member not found'}, status=404)

    # Get filter parameter
    filter_type = request.GET.get('filter', 'all')
    
    # Calculate date range based on filter
    now = timezone.now()
    if filter_type == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif filter_type == 'quarter':
        current_quarter = (now.month - 1) // 3 + 1
        start_date = now.replace(month=3 * current_quarter - 2, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif filter_type == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # all
        start_date = None

    # Get all events for the organization
    events = Event.objects.filter(organization=org)
    if start_date:
        events = events.filter(date__gte=start_date)
    
    total_events = events.count()
    
    # Get events where the member has attendance records
    member_events = Event.objects.filter(
        organization=org,
        attendance__user=member,
        attendance__is_attending=True
    )
    if start_date:
        member_events = member_events.filter(date__gte=start_date)
    
    attended_count = member_events.count()
    
    # Calculate attendance rate
    attendance_rate = round((attended_count / total_events * 100) if total_events > 0 else 0)
    
    # Get last attended date
    last_attended = member_events.order_by('-date').first()
    last_attended_date = last_attended.date.strftime('%m/%d/%Y') if last_attended else 'Never'
    
    # Get attendance history
    attendance_history = []
    for event in events.order_by('-date'):
        attended = EventAttendance.objects.filter(
            event=event,
            user=member,
            is_attending=True
        ).exists()
        
        attendance_history.append({
            'name': event.name,
            'date': event.date.strftime('%m/%d/%Y'),
            'attended': attended
        })
    
    return JsonResponse({
        'name': f"{member.f_name} {member.l_name}",
        'total_events': total_events,
        'attended_events': attended_count,
        'attendance_rate': attendance_rate,
        'last_attended': last_attended_date,
        'attendance_history': attendance_history
    })
