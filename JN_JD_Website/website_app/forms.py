from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User, Organization, Event, Group, Geofence
from django.db.models import Q

class SignInForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply CSS classes to text fields only
        self.fields['username'].widget.attrs.update({'class': 'textbox', 'placeholder':'Username'})
        self.fields['password'].widget.attrs.update({'class': 'textbox', 'placeholder':'Password'})

        for field in self.fields.values():
            field.label = ''

class CreateAccountForm(UserCreationForm):
    f_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'First Name'})
    )
    l_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Last Name'})
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Username'})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'textbox', 'placeholder': 'Password'})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'textbox', 'placeholder': 'Confirm Password'})
    )
    remember_me = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput()
    )

    class Meta:
        model = User
        fields = ['f_name', 'l_name', 'username', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.label = ''

class CreateOrganizationForm(forms.ModelForm):
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Organization Name'})
    )

    class Meta:
        model = Organization
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.label = ''

class CreateEventForm(forms.ModelForm):
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Event Name'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'textbox', 'placeholder': 'Event Description', 'rows': 4})
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'textbox', 'type': 'date'})
    )
    location = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Event Location'})
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        widget=forms.Select(attrs={'class': 'textbox'}),
        empty_label="Select Organization"
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Groups"
    )
    # Geofence fields
    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'textbox', 'step': '0.000001'})
    )
    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'textbox', 'step': '0.000001'})
    )
    radius = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'textbox', 'placeholder': 'Radius (meters)'})
    )

    class Meta:
        model = Event
        fields = ['name', 'description', 'date', 'location', 'organization', 'groups', 'latitude', 'longitude', 'radius']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set organization queryset based on user
        if user:
            self.fields['organization'].queryset = Organization.objects.filter(
                Q(owner=user) | Q(user_organizations__user=user)
            ).distinct()
            
            # Set groups queryset based on selected organization
            if 'organization' in self.data:
                try:
                    org_id = int(self.data.get('organization'))
                    self.fields['groups'].queryset = Group.objects.filter(organization_id=org_id)
                except (ValueError, TypeError):
                    pass
            elif self.instance.pk:
                self.fields['groups'].queryset = self.instance.organization.groups.all()

        for field in self.fields.values():
            field.label = ''

    def save(self, commit=True):
        event = super().save(commit=False)
        event.geofence_latitude = self.cleaned_data['latitude']
        event.geofence_longitude = self.cleaned_data['longitude']
        event.geofence_radius = self.cleaned_data['radius']
        
        if commit:
            event.save()
            self.save_m2m()
        return event

    def clean_latitude(self):
        lat = self.cleaned_data.get('latitude')
        if lat is None:
            raise forms.ValidationError('Latitude is required.')
        return lat

    def clean_longitude(self):
        lon = self.cleaned_data.get('longitude')
        if lon is None:
            raise forms.ValidationError('Longitude is required.')
        return lon

class CreateGroupForm(forms.ModelForm):
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Group Name'})
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),  # Default to an empty queryset
        widget=forms.Select(attrs={'class': 'textbox'}),
        empty_label="Select Organization"
    )

    class Meta:
        model = Group
        fields = ['name', 'organization']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Extract user from kwargs
        super().__init__(*args, **kwargs)

        if user:
            self.fields['organization'].queryset = Organization.objects.filter(owner=user)  # Show only user's organizations

        for field in self.fields.values():
            field.label = ''

class JoinOrganizationForm(forms.Form):
    invite_code = forms.CharField(
        max_length=10,
        label="Organization Invite Code",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter invite code'})
    )

    def clean_invite_code(self):
        invite_code = self.cleaned_data.get('invite_code')
        if not Organization.objects.filter(invite_code=invite_code).exists():
            raise forms.ValidationError("Invalid invite code. Please try again.")
        return invite_code

class CreateGeofenceForm(forms.ModelForm):
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Geofence Name'})
    )
    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(attrs={'class': 'textbox', 'placeholder': 'Latitude', 'step': '0.000001'})
    )
    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(attrs={'class': 'textbox', 'placeholder': 'Longitude', 'step': '0.000001'})
    )
    radius = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'textbox', 'placeholder': 'Radius (meters)'})
    )
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        widget=forms.Select(attrs={'class': 'textbox'}),
        empty_label="Select Event"
    )

    class Meta:
        model = Geofence
        fields = ['name', 'latitude', 'longitude', 'radius', 'event']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # Filter events to those owned by the current user
            self.fields['event'].queryset = Event.objects.filter(owner=user)

        for field in self.fields.values():
            field.label = ''