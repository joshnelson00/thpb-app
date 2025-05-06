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
from .models import Organization, Event, UserGroups, EventGroups, UserOrganization, Group, User, EventCheckIn
from django.http import Http404
from django.conf import settings
from django.views.decorators.http import require_POST
from django.utils import timezone
import math



@login_required
def home(request):
    # Get the next 3 upcoming events for the user
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
    upcoming_events = Event.objects.filter(
        groups__in=user_groups,
        date__gte=timezone.now()
    ).order_by('date')[:3]

    # Calculate time until event for each event
    for event in upcoming_events:
        event_datetime = timezone.make_aware(
            timezone.datetime.combine(event.date, timezone.datetime.min.time())
        )
        time_until = event_datetime - timezone.now()
        event.minutes_until = int(time_until.total_seconds() / 60)

    # Get user's groups with their roles
    user_groups = UserGroups.objects.filter(user=request.user).select_related('group', 'group__organization')

    # Get organizations owned by the user
    owned_organizations = Organization.objects.filter(owner=request.user).prefetch_related('groups')

    # Get organizations where user is a member (but not owner)
    member_organizations = Organization.objects.filter(
        user_organizations__user=request.user
    ).exclude(owner=request.user).prefetch_related('groups')

    context = {
        'upcoming_events': upcoming_events,
        'user_groups': user_groups,
        'owned_organizations': owned_organizations,
        'member_organizations': member_organizations,
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
                form.add_error(None, "Invalid credentials.")
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
        form = CreateEventForm(request.POST, user=request.user, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.save()
            
            return redirect('viewevents')  # Redirect to the view events page
    else:
        form = CreateEventForm(user=request.user, instance=event)

    # Get all groups from the event's organization
    available_groups = Group.objects.filter(organization=event.organization).exclude(
        id__in=EventGroups.objects.filter(event=event).values_list('group_id', flat=True)
    )
    
    # Get groups already assigned to the event using EventGroups
    assigned_groups = Group.objects.filter(
        id__in=EventGroups.objects.filter(event=event).values_list('group_id', flat=True)
    )

    context = {
        'form': form,
        'event': event,
        'available_groups': available_groups,
        'assigned_groups': assigned_groups
    }

    return render(request, 'editevent.html', context)


@login_required
def view_events(request):
    # Get organizations the user owns
    owned_organizations = Organization.objects.filter(owner=request.user)

    if owned_organizations.exists():
        events = Event.objects.filter(
            organization__in=owned_organizations,
            date__gte=timezone.now().date()  # Convert datetime to date for comparison
        ).prefetch_related('groups').distinct()
    else:
        user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)
        events = Event.objects.filter(
            id__in=EventGroups.objects.filter(group__in=user_groups).values_list('event', flat=True),
            date__gte=timezone.now().date()  # Convert datetime to date for comparison
        ).prefetch_related('groups').distinct()

    organization_id = request.GET.get('organization_id')
    group_id = request.GET.get('group_id')

    if organization_id:
        events = events.filter(organization_id=organization_id)
    if group_id:
        events = events.filter(groups__id=group_id).distinct()

    # Sort by date ascending (earliest to latest)
    events = events.order_by('date')

    # Get the groups for each event through EventGroups
    for event in events:
        event.attending_groups = Group.objects.filter(
            id__in=EventGroups.objects.filter(event=event).values_list('group_id', flat=True)
        )
        
        # Create a datetime object for the event (using noon as default time)
        event_datetime = timezone.make_aware(
            datetime.combine(event.date, datetime_time(12, 0))
        )
        
        # Calculate time until event
        time_until = event_datetime - timezone.now()
        event.minutes_until = int(time_until.total_seconds() / 60)
        
        # Calculate time display
        if event.minutes_until >= 1440:  # More than 24 hours
            days = event.minutes_until // 1440
            remaining_minutes = event.minutes_until % 1440
            hours = remaining_minutes // 60
            event.time_display = f"{days}d {hours}h until event"
        elif event.minutes_until >= 60:  # More than 1 hour
            hours = event.minutes_until // 60
            minutes = event.minutes_until % 60
            event.time_display = f"{hours}h {minutes}m until event"
        else:  # Less than 1 hour
            event.time_display = f"{event.minutes_until}m until event"
            
        event.can_check_in = -30 <= event.minutes_until <= 0  # Can check in 30 minutes before event
        event.is_past = event.minutes_until < -30  # Event is past if more than 30 minutes old
        
        # Get check-in status for current user
        event.user_check_in = EventCheckIn.objects.filter(
            event=event,
            user=request.user,
            is_within_radius=True
        ).first()

    context = {
        'events': events,
        'organizations': Organization.objects.filter(groups__in=user_groups).distinct() if not owned_organizations.exists() else owned_organizations,
        'selected_organization_id': organization_id,
        'selected_group_id': group_id,
    }

    return render(request, 'viewevents.html', context)





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
            
            # Optionally, add a success message
            messages.success(request, f"You've successfully created {organization.name} and joined it!")

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
            try:
                event = form.save(commit=False)
                event.owner = request.user
                event.save()
                form.save_m2m()  # Save many-to-many relationships (groups)
                messages.success(request, 'Event created successfully!')
                return redirect('viewevents')  # Changed from 'events' to 'viewevents'
            except Exception as e:
                messages.error(request, f'Error creating event: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CreateEventForm(user=request.user)
    
    return render(request, 'createevent.html', {
        'form': form,
        'page_title': 'Create Event'
    })

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
        # Try to handle both JSON and form data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                print("JSON decode error")
                return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
        else:
            data = request.POST

        group_id = data.get("group_id")
        event_id = data.get("event_id")
        action = data.get("action")

        # Validate required fields
        if not group_id or not group_id.isdigit():
            return JsonResponse({"success": False, "error": "Invalid group ID"}, status=400)
        if not event_id or not event_id.isdigit():
            return JsonResponse({"success": False, "error": "Invalid event ID"}, status=400)
        if not action:
            return JsonResponse({"success": False, "error": "Action is required"}, status=400)

        group = get_object_or_404(Group, id=int(group_id))
        event = get_object_or_404(Event, id=int(event_id))

        # Ensure the user has permission to modify this event
        if event.owner != request.user:
            return JsonResponse({"success": False, "error": "You don't have permission to modify this event"}, status=403)

        if action == "add":
            # Add group to event
            EventGroups.objects.get_or_create(group=group, event=event)
            return JsonResponse({
                "success": True,
                "message": f"Group {group.name} added to event {event.name}"
            })
        elif action == "remove":
            # Remove group from event
            EventGroups.objects.filter(group=group, event=event).delete()
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
    try:
        event = get_object_or_404(Event, id=event_id, owner=request.user)
        event.delete()
        return redirect('viewevents')  # Redirect to the events page after deletion
    except Exception as e:
        messages.error(request, f'Error deleting event: {str(e)}')
        return redirect('viewevents')

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
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if not latitude or not longitude:
            return JsonResponse({'error': 'Location data is required'}, status=400)

        # Calculate time until event
        time_until = event.date - timezone.now()
        minutes_until = int(time_until.total_seconds() / 60)

        # Check if user can check in (30 minutes before event)
        if minutes_until > 0:
            return JsonResponse({
                'error': 'Check-in is only available 30 minutes before the event starts',
                'minutes_until': minutes_until
            }, status=400)
        
        if minutes_until < -30:
            return JsonResponse({
                'error': 'Event has already ended',
                'minutes_until': minutes_until
            }, status=400)

        # Calculate distance from event location
        distance = calculate_distance(
            event.geofence_latitude,
            event.geofence_longitude,
            latitude,
            longitude
        )

        is_within_radius = distance <= event.geofence_radius

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

        return JsonResponse({
            'success': True,
            'is_within_radius': is_within_radius,
            'distance': round(distance, 2),
            'message': 'Check-in successful' if is_within_radius else 'You are not within the event radius'
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
        raise Http404("You don't have permission to view this event's attendance.")
    
    # Get all users who should attend (from groups assigned to the event)
    expected_attendees = User.objects.filter(
        groups__in=event.groups.all()
    ).distinct()
    
    # Get all check-ins for this event
    check_ins = EventCheckIn.objects.filter(
        event=event,
        is_within_radius=True
    ).select_related('user')
    
    # Create attendance lists
    attended = [check_in.user for check_in in check_ins]
    absent = [user for user in expected_attendees if user not in attended]
    
    context = {
        'event': event,
        'attended': attended,
        'absent': absent,
        'total_expected': len(expected_attendees),
        'total_attended': len(attended),
        'attendance_rate': (len(attended) / len(expected_attendees) * 100) if expected_attendees else 0
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
