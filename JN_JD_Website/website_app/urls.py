from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.sign_in, name='signin'),
    path('createaccount/', views.create_account, name='createaccount'),  # Corrected view name to match
    path('home/', views.home, name='home'),
    path('logout/', LogoutView.as_view(next_page='signin'), name='logout'),
    path('editgroups/<int:org_id>/', views.edit_groups, name='editgroups'),
    path('editevent/<int:event_id>/', views.edit_event, name='editevent'),
    path('delete_event/<int:event_id>/', views.delete_event, name='delete_event'),
    path('viewevents/', views.view_events, name='viewevents'),
    path('events/', views.view_events, name='viewevents'),
    path('events/past/', views.view_past_events, name='pastevents'),
    path('createorg/', views.create_org, name='createorg'),
    path('creategroup/', views.create_group, name='creategroup'),
    path('createevent/', views.create_event, name='createevent'),
    path('vieworgs/', views.view_organizations, name='vieworgs'),
    path('joinorg/', views.join_org, name='joinorg'),
    path('deleteorg/<int:org_id>/', views.delete_organization, name='delete_organization'),
    path("update-user-group/", views.update_user_group, name="update_user_group"),
    path("add-user-to-group/", views.add_user_to_group, name="add_user_to_group"),
    path("remove-user-from-group/", views.remove_user_from_group, name="remove_user_from_group"),
    path("update-group-name/", views.update_group_name, name="update_group_name"),
    path('get_groups_by_org/<int:org_id>/', views.get_groups_by_org, name='get_groups_by_org'),
    path("update-event-group/", views.update_event_group, name="update_event_group"),
    path('update-user-location/', views.update_user_location, name='update_user_location'),
    path('event/<int:event_id>/check-in/', views.check_in_to_event, name='check_in_to_event'),
    path('event/<int:event_id>/attendance/', views.event_attendance, name='event_attendance'),
    path('event/<int:event_id>/checkin-page/', views.event_checkin_page, name='event_checkin_page'),
    path('account/', views.account_details, name='account_details'),
    path('notifications/', views.notifications, name='notifications'),
    path('settings/', views.settings, name='settings'),
    path('help/', views.help_support, name='help'),
    
    # Announcement URLs
    path('announcements/', views.view_announcements, name='view_announcements'),
    path('organization/<int:org_id>/create-announcement/', views.create_announcement, name='create_announcement'),
    path('organization/<int:org_id>/announcements/', views.get_announcements, name='get_announcements'),
    path('announcement/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('announcement/<int:announcement_id>/edit/', views.edit_announcement, name='edit_announcement'),
    path('announcement/<int:announcement_id>/files/', views.get_announcement_files, name='get_announcement_files'),
    path('announcement/<int:announcement_id>/details/', views.get_announcement_details, name='get_announcement_details'),
    
    # Password Reset URLs
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='password_reset.html',
        email_template_name='password_reset_email.html',
        subject_template_name='password_reset_subject.txt'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='password_reset_complete.html'
    ), name='password_reset_complete'),
    path('update-group-color/', views.update_group_color, name='update_group_color'),
]
