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
from .models import Organization, Event, UserGroups, EventGroups, UserOrganization, Group, User, EventCheckIn, EventAttendance, Announcement, AnnouncementFile, EventAttendees
from django.http import Http404
from django.conf import settings
from django.views.decorators.http import require_POST
from django.utils import timezone
import math
from django.db.models import Q
import pytz
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied



@login_required
def home(request):
    # Get organizations owned by the user
    owned_organizations = Organization.objects.filter(owner=request.user)
    
    # Get user's groups
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    
    # Get current time in UTC
    current_time = timezone.now()
    
    # Base query for events - same as view_events
    events_query = Event.objects.filter(
        Q(groups__group__in=user_groups) |  # Events where user's groups are attending
        Q(organization__in=owned_organizations)  # Events from organizations user owns
    ).distinct()
    
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
            # Get attending groups for the event - include both initially assigned groups and groups from attendees
            event.attending_groups = []
            # Add initially assigned groups
            for event_group in event.groups.all():
                event.attending_groups.append({
                    'name': event_group.group.name,
                    'color': event_group.group.color
                })
            # Add groups from attendees that aren't already included
            for attendee in event.attendees.all():
                if attendee.group and not any(g['name'] == attendee.group.name for g in event.attending_groups):
                    event.attending_groups.append({
                        'name': attendee.group.name,
                        'color': attendee.group.color
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
            
            upcoming_events.append(event)
            
            # Break after getting 3 events
            if len(upcoming_events) >= 3:
                break

    # Get user's groups with their roles
    user_groups = UserGroups.objects.filter(user=request.user).select_related('group', 'group__organization')

    # Get organizations where user is a member (but not owner)
    member_organizations = Organization.objects.filter(
        user_organizations__user=request.user
    ).exclude(owner=request.user).prefetch_related('groups')

    # Get all announcements from organizations the user has access to
    announcements = Announcement.objects.filter(
        organization__in=list(owned_organizations) + list(member_organizations),
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

    context = {
        'form': form,
        'event': event,
        'attending_users': attending_users,
        'available_users': available_users,
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
    view_type = request.GET.get('view', 'all')
    
    # Fetch organizations where the current user is the owner
    owned_organizations = Organization.objects.filter(owner=request.user)
    
    # Fetch organizations where the current user is a member (but not the owner)
    member_organizations = Organization.objects.filter(user_organizations__user=request.user).exclude(owner=request.user)
    
    # For owned organizations, fetch groups where the user is the owner
    owned_groups = Group.objects.filter(owner=request.user)
    
    # Fetch user's groups in organizations
    user_groups = UserGroups.objects.filter(user=request.user).select_related('group', 'group__organization')
    
    # Pass the context data
    context = {
        'owned_organizations': owned_organizations,
        'member_organizations': member_organizations,
        'owned_groups': owned_groups,
        'user_groups': user_groups,
        'view_type': view_type
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

        if not all([group_id, event_id, action]):
            return JsonResponse({"success": False, "error": "Missing required parameters"}, status=400)

        # Get the event and verify ownership
        event = get_object_or_404(Event, id=event_id, owner=request.user)
        group = get_object_or_404(Group, id=group_id)

        if action == "add":
            # Add group to event
            EventGroups.objects.get_or_create(group=group, event=event)
            # Add all users from the group as attendees
            group_users = UserGroups.objects.filter(group=group)
            for user_group in group_users:
                EventAttendees.objects.get_or_create(
                    event=event,
                    user=user_group.user,
                    group=group
                )
            return JsonResponse({
                "success": True,
                "message": f"Group {group.name} added to event {event.name}"
            })
        elif action == "remove":
            # Remove group from event
            EventGroups.objects.filter(group=group, event=event).delete()
            # Remove attendees from the removed group
            EventAttendees.objects.filter(event=event, group=group).delete()
            return JsonResponse({
                "success": True,
                "message": f"Group {group.name} removed from event {event.name}"
            })
        else:
            return JsonResponse({"success": False, "error": "Invalid action"}, status=400)

    except Exception as e:
        print(f"Unexpected error: {e}")
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
    
    # Get all groups assigned to this event through EventGroups
    event_groups = Group.objects.filter(events__event=event)
    
    # Get all users who should attend (from groups assigned to the event)
    expected_attendees = User.objects.filter(
        membership_groups__group__in=event_groups
    ).exclude(id=event.owner.id).distinct()  # Exclude the event owner
    
    # Get all check-ins for this event
    check_ins = EventCheckIn.objects.filter(
        event=event,
        is_within_radius=True
    ).select_related('user').exclude(user=event.owner)  # Exclude the event owner
    
    # Create attendance lists
    attended = [check_in.user for check_in in check_ins]
    absent = [user for user in expected_attendees if user not in attended]
    
    # Calculate attendance rate safely
    total_expected = len(expected_attendees)
    total_attended = len(attended)
    attendance_rate = (total_attended / total_expected * 100) if total_expected > 0 else 0
    
    context = {
        'event': event,
        'attended': attended,
        'absent': absent,
        'total_expected': total_expected,
        'total_attended': total_attended,
        'attendance_rate': attendance_rate
    }
    
    return render(request, 'event_attendance.html', context)

@login_required
def account_details(request):
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
def event_checkin_page(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is in any of the groups attending the event
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    event_groups = EventGroups.objects.filter(event=event).values_list('group', flat=True)
    user_can_attend = any(group in event_groups for group in user_groups)
    
    if not user_can_attend:
        messages.error(request, "You are not authorized to check in to this event.")
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
    
    # Debug prints
    print(f"Current time (Event TZ): {current_time}")
    print(f"Event time (Event TZ): {event_datetime}")
    print(f"Minutes until event: {minutes_until}")
    print(f"Can check in: {-30 <= minutes_until <= 30}")
    
    # Format time display
    if minutes_until >= 1440:  # More than 24 hours
        days = minutes_until // 1440
        hours = (minutes_until % 1440) // 60
        time_display = f"{days}d {hours}h"
    elif minutes_until >= 60:  # More than 1 hour
        hours = minutes_until // 60
        minutes = minutes_until % 60
        time_display = f"{hours}h {minutes}m"
    else:
        time_display = f"{minutes_until}m"
    
    # Set can_check_in property on the event object
    event.minutes_until = minutes_until
    event.time_display = time_display
    event.can_check_in = -30 <= minutes_until <= 30
    
    # Check if user has already checked in
    event.user_check_in = EventCheckIn.objects.filter(
        event=event,
        user=request.user,
        is_within_radius=True
    ).exists()
    
    # Get attending groups for the event
    event.attending_groups = [{'name': event_group.group.name, 'color': event_group.group.color} for event_group in event.groups.all()]
    
    context = {
        'event': event,
    }
    
    return render(request, 'event_checkin.html', context)

# TODO: AWS S3 Implementation Considerations
# 1. Update file upload handling to work with S3:
#    - Consider using pre-signed URLs for direct uploads
#    - Implement proper error handling for S3 operations
#    - Add file size and type validation
#
# 2. Update file download handling:
#    - Generate signed URLs for secure file access
#    - Implement proper error handling for S3 operations
#    - Consider implementing file streaming for large files
#
# 3. Security considerations:
#    - Implement proper access controls
#    - Set up bucket policies
#    - Consider implementing file encryption
#    - Add rate limiting for file operations
#
# 4. Performance optimizations:
#    - Consider implementing caching
#    - Add CDN integration if needed
#    - Implement file compression if needed

@login_required
@require_POST
def create_announcement(request, org_id):
    try:
        # Get the organization and verify ownership
        organization = get_object_or_404(Organization, id=org_id)
        if organization.owner != request.user:
            return JsonResponse({'error': 'You do not have permission to create announcements'}, status=403)

        # Get data from request
        data = request.POST
        files = request.FILES.getlist('files')

        # Create the announcement
        announcement = Announcement.objects.create(
            organization=organization,
            title=data.get('title'),
            content=data.get('content'),
            created_by=request.user,
            is_active=True
        )

        # Handle file uploads
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
def get_announcements(request, org_id):
    try:
        # Get the organization
        organization = get_object_or_404(Organization, id=org_id)
        
        # Verify user is a member or owner of the organization
        if not (organization.owner == request.user or UserOrganization.objects.filter(user=request.user, organization=organization).exists()):
            return JsonResponse({'error': 'You do not have permission to view announcements'}, status=403)

        # Get page number from query params
        page = int(request.GET.get('page', 1))
        per_page = 10
        start = (page - 1) * per_page
        end = start + per_page

        # Get announcements
        announcements = organization.announcements.filter(
            is_active=True
        ).select_related('created_by').prefetch_related('files')[start:end]

        # Format announcements for JSON response
        announcements_data = []
        for announcement in announcements:
            files_data = [{
                'url': file.file.url,
                'filename': file.filename
            } for file in announcement.files.all()]

            announcements_data.append({
                'id': announcement.id,
                'title': announcement.title,
                'content': announcement.content,
                'created_at': announcement.created_at.strftime('%b %d, %Y'),
                'created_by': announcement.created_by.get_full_name() or announcement.created_by.username,
                'files': files_data
            })

        return JsonResponse({'announcements': announcements_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def delete_announcement(request, announcement_id):
    try:
        # Get the announcement
        announcement = get_object_or_404(Announcement, id=announcement_id)
        
        # Verify ownership
        if announcement.organization.owner != request.user:
            return JsonResponse({'error': 'You do not have permission to delete this announcement'}, status=403)

        # Soft delete by marking as inactive
        announcement.is_active = False
        announcement.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        event_id = data.get('event_id')
        action = data.get('action')

        if not all([user_id, event_id, action]):
            return JsonResponse({"success": False, "error": "Missing required parameters"}, status=400)

        event = get_object_or_404(Event, id=event_id, owner=request.user)
        user = get_object_or_404(User, id=user_id)

        if action == "add":
            # Add user to attendees
            EventAttendees.objects.get_or_create(event=event, user=user)
            return JsonResponse({
                "success": True,
                "message": f"User {user.f_name} {user.l_name} added to event {event.name}"
            })
        elif action == "remove":
            # Remove user from attendees
            EventAttendees.objects.filter(event=event, user=user).delete()
            return JsonResponse({
                "success": True,
                "message": f"User {user.f_name} {user.l_name} removed from event {event.name}"
            })
        else:
            return JsonResponse({"success": False, "error": "Invalid action"}, status=400)

    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
