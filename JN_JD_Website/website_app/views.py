from django.utils.timezone import now
from django.contrib import messages
import time

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SignInForm, CreateAccountForm, CreateOrganizationForm, CreateGroupForm, CreateEventForm, JoinOrganizationForm
from django.views.decorators.csrf import csrf_exempt
from .models import Organization, Event, UserGroups, EventGroups, UserOrganization, Group, User
from django.http import Http404



@login_required
def home(request):
    # You can populate the context with data specific to the user or the page
    context = {}
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
            user = form.save(commit=False)  # Create user but don’t save yet
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
        users_in_groups[group.id] = group.user_groups.values_list('user', flat=True)

    # Get users who are not in any group in this organization
    users_not_in_groups = User.objects.exclude(id__in=[user_id for user_list in users_in_groups.values() for user_id in user_list]).all()

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
            messages.success(request, f"{user.username} was added to {group.name}.")
        elif action == "remove" and group_id and user_id:
            user = get_object_or_404(User, id=user_id)
            group = get_object_or_404(Group, id=group_id)
            
            # Remove the user from the group
            deleted_count, _ = UserGroups.objects.filter(user=user, group=group).delete()
            if deleted_count:
                messages.success(request, f"{user.username} was removed from {group.name}.")
            else:
                messages.warning(request, f"{user.username} was not found in {group.name}.")
    
    # Prepare context for rendering the template
    context = {
        'organization': organization,
        'groups': groups,
        'users_in_groups': users_in_groups,
        'users_not_in_groups': users_not_in_groups,
    }
    return render(request, 'editgroups.html', context)

@login_required
@csrf_exempt
def update_user_group(request):
    print("POST data received:", request.POST)

    user_id = request.POST.get('user_id')
    group_id = request.POST.get('group_id', None)
    action = request.POST.get('action')

    # Ensure user_id is valid
    if not user_id or not user_id.isdigit():
        return JsonResponse({"success": False, "message": "Invalid user ID"}, status=400)

    # Ensure group_id is valid
    if action == "add" and (not group_id or not group_id.isdigit()):
        return JsonResponse({"success": False, "message": "Invalid group ID"}, status=400)

    user = get_object_or_404(User, id=int(user_id))
    print(f"User found: {user}")

    response = {}

    if action == "add":
        group = get_object_or_404(Group, id=int(group_id))
        print(f"Group found: {group}")

        role = request.POST.get('role')
        print(f"Role: {role}")

        UserGroups.objects.get_or_create(user=user, group=group, role=role)
        response["success"] = True
        response["message"] = "User added to group successfully."
        print("User added to group.")

    elif action == "remove":
        deleted_count, _ = UserGroups.objects.filter(user=user, group__id=group_id).delete()
        if deleted_count:
            response["success"] = True
            response["message"] = "User removed from group successfully."
            print("User removed from group.")
        else:
            response["success"] = False
            response["message"] = "User not found in the specified group."
            print("User not found in group.")

    print("Response:", response)
    return JsonResponse(response)



def update_group_name(request):
    group_name = request.POST.get('groupName')
    group_id = request.POST.get('groupId')  # Get the group ID if needed

    group = Group.objects.get(id=group_id)
    group.name = group_name
    group.save()

    return JsonResponse({"success": True, "message": "Group name updated successfully."})


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

            # Clear existing group associations and add the new ones
            event.groups.clear()
            event.groups.add(*form.cleaned_data['groups'])
            
            return redirect('viewevents')  # Redirect to the view events page
    else:
        form = CreateEventForm(user=request.user, instance=event)

    context = {
        'form': form,
        'event': event
    }

    return render(request, 'editevent.html', context)


@login_required
def view_events(request):
    # Get the groups the user is a member of
    user_groups = UserGroups.objects.filter(user=request.user).values_list('group', flat=True)

    # Get events associated with the user's groups
    events = Event.objects.filter(
    id__in=EventGroups.objects.filter(group__in=user_groups).values_list('event', flat=True),date__gte=now()).distinct()


    # Optional filtering by organization or group
    organization_id = request.GET.get('organization_id')
    group_id = request.GET.get('group_id')

    if organization_id:
        events = events.filter(organization_id=organization_id)
    if group_id:
        events = events.filter(groups__id=group_id).distinct()

    # Attach attending groups to each event
    for event in events:
        event.attending_groups = Group.objects.filter(events__event=event)


    context = {
        'events': events,
        'organizations': Organization.objects.filter(groups__in=user_groups).distinct(),
        'selected_organization_id': organization_id,
        'selected_group_id': group_id,
    }

    return render(request, 'viewevents.html', context)




@login_required
def view_organizations(request):
    # Fetch organizations where the current user is the owner
    owned_organizations = Organization.objects.filter(owner=request.user)
    
    # Fetch organizations where the current user is a member (but not the owner)
    member_organizations = Organization.objects.filter(user_organizations__user=request.user).exclude(owner=request.user)
    
    # For owned organizations, fetch groups where the user is the owner
    owned_groups = Group.objects.filter(owner=request.user)
    
    # Pass the owned groups to the context as well
    context = {
        'owned_organizations': owned_organizations,
        'member_organizations': member_organizations,
        'owned_groups': owned_groups
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

def get_groups_by_org(request, org_id):
    organization = get_object_or_404(Organization, id=org_id)
    groups = organization.groups.all()
    group_data = [{"id": group.id, "name": group.name} for group in groups]
    return JsonResponse({'groups': group_data})


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
    if request.method == "POST":
        form = CreateEventForm(data=request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.owner = request.user
            event.save()

            # Create EventGroups associations for the selected groups
            selected_groups = form.cleaned_data.get('groups')
            if selected_groups:
                for group in selected_groups:
                    EventGroups.objects.create(group=group, event=event)

            # Redirect to home page after successful form submission
            return redirect('home')
        else:
            print(form.errors)  # Print form errors for debugging
    else:
        # Initialize the form and call update_groups to update available groups
        form = CreateEventForm(user=request.user)

        # If the organization is selected through GET (via AJAX or other means)
        organization_id = request.GET.get('organization_id')
        if organization_id:
            form.update_groups(organization_id)

    context = {
        'form': form,
    }
    
    return render(request, 'createevent.html', context)
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