# JN_JD_Website

A comprehensive event management system built with Django, designed to handle organization events, group management, and attendance tracking.

## Features

### Organization Management
- Create and manage organizations
- Generate unique invite codes for organization membership
- Role-based access control
- Organization-wide announcements

### Group Management
- Create and manage groups within organizations
- Custom group colors for visual organization
- Add/remove members from groups
- Role assignment within groups

### Event Management
- Create and schedule events
- Set event locations with geofencing
- Timezone support
- Group-based event attendance
- Event check-in system with location verification
- Past events archive

### Substitution System
- Request substitutions for events
- Accept/reject substitution requests
- Manage substitutions between users
- Track substitution history

### User Features
- User authentication and authorization
- Profile management
- Location tracking for event check-ins
- Notification system
- Password reset functionality

## Technical Stack

- **Backend**: Django
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite (default) / PostgreSQL
- **Authentication**: Django's built-in authentication system
- **Location Services**: Geofencing for event check-ins

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/joshnelson00/JN_JD_Website.git
cd JN_JD_Website
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Project Structure

```
JN_JD_Website/
├── website_app/
│   ├── templates/          # HTML templates
│   ├── static/            # Static files (CSS, JS)
│   ├── models.py          # Database models
│   ├── views.py           # View logic
│   ├── urls.py            # URL routing
│   └── forms.py           # Form definitions
├── manage.py              # Django management script
└── requirements.txt       # Project dependencies
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For any questions or concerns, please open an issue in the GitHub repository.