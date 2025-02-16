from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User, Organization, Event, Group

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
        required=False,
        widget=forms.TextInput(attrs={'class': 'textbox', 'placeholder': 'Location (Optional)'})
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

    class Meta:
        model = Event
        fields = ['name', 'description', 'date', 'location', 'organization', 'groups']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Extract user from kwargs
        super().__init__(*args, **kwargs)

        if user:
            # Filter organizations to those owned by the current user
            self.fields['organization'].queryset = Organization.objects.filter(owner=user)
        
        # Dynamically populate groups based on the selected organization
        organization = self.initial.get('organization', None) or self.data.get('organization', None)
        if organization:
            # If organization is selected, filter groups based on the selected organization
            self.fields['groups'].queryset = Group.objects.filter(organization_id=organization)

        for field in self.fields.values():
            field.label = ''







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