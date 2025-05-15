from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.sign_in, name='signin'),
    path('createaccount/', views.create_account, name='createaccount'),
    path('home/', views.home, name='home'),
    path('logout/', LogoutView.as_view(next_page='signin'), name='logout'),
    path('editgroups/<int:org_id>/', views.edit_groups, name='editgroups'),
    path('editevent/<int:event_id>/', views.edit_event, name='editevent'),
    path('delete_event/<int:event_id>/', views.delete_event, name='delete_event'),
    path('update_org_name/<int:org_id>/', views.update_org_name, name='update_org_name'),
    path('viewevents/', views.view_events, name='viewevents'),
    path('events/', views.view_events, name='viewevents'),
    path('events/past/', views.view_past_events, name='pastevents'),
    path('createorg/', views.create_org, name='createorg'),
    path('creategroup/', views.create_group, name='creategroup'),
    path('createevent/', views.create_event, name='createevent'),
    path('vieworgs/', views.view_organizations, name='vieworgs'),
    path('joinorg/', views.join_org, name='joinorg'),
    path('deleteorg/<int:org_id>/', views.delete_organization, name='deleteorg'),
    path('about/', views.about, name='about'),
    path('account/', views.account_details, name='account'),
    path('notifications/', views.notifications, name='notifications'),
    path('settings/', views.settings, name='settings'),
    path('help/', views.help_support, name='help'),
    path('get_groups/<int:org_id>/', views.get_groups_by_org, name='get_groups'),
    path('update_user_group/', views.update_user_group, name='update_user_group'),
    path('update_group_name/', views.update_group_name, name='update_group_name'),
    path('add_user_to_group/', views.add_user_to_group, name='add_user_to_group'),
    path('remove_user_from_group/', views.remove_user_from_group, name='remove_user_from_group'),
    path('update_event_group/', views.update_event_group, name='update_event_group'),
    path('update_user_location/', views.update_user_location, name='update_user_location'),
    path('check_in/<int:event_id>/', views.check_in_to_event, name='check_in'),
    path('event_attendance/<int:event_id>/', views.event_attendance, name='event_attendance'),
    path('get_substitution_requests/', views.get_substitution_requests, name='get_substitution_requests'),
    path('request_substitution/', views.request_substitution, name='request_substitution'),
    path('view_announcements/', views.view_announcements, name='view_announcements'),
    path('edit_announcement/<int:announcement_id>/', views.edit_announcement, name='edit_announcement'),
    path('get_announcement_files/<int:announcement_id>/', views.get_announcement_files, name='get_announcement_files'),
    path('get_announcement_details/<int:announcement_id>/', views.get_announcement_details, name='get_announcement_details'),
    path('update_group_color/', views.update_group_color, name='update_group_color'),
    path('update_event_attendee/', views.update_event_attendee, name='update_event_attendee'),
    path('get_group_members/<int:group_id>/', views.get_group_members, name='get_group_members'),
    path('add_substitution/', views.add_substitution, name='add_substitution'),
    path('remove_substitution/<int:substitution_id>/', views.remove_substitution, name='remove_substitution'),
    path('view_event/<int:event_id>/', views.view_event, name='view_event'),
    path('event_checkin/<int:event_id>/', views.event_checkin_page, name='event_checkin'),
    path('create_announcement/<int:org_id>/', views.create_announcement, name='create_announcement'),
    path('get_announcements/<int:org_id>/', views.get_announcements, name='get_announcements'),
    path('delete_announcement/<int:announcement_id>/', views.delete_announcement, name='delete_announcement'),
    path('pending_substitution_requests/', views.pending_substitution_requests, name='pending_substitution_requests'),
    path('get_user_group/<int:event_id>/', views.get_user_group, name='get_user_group'),
    path('request_sub/<int:event_id>/', views.request_sub, name='request_sub'),
    path('respond_to_substitution_request/<int:request_id>/', views.respond_to_substitution_request, name='respond_to_substitution_request'),
    path('manage_tags/<int:org_id>/', views.manage_tags, name='manage_tags'),
    path('update_user_tag/', views.update_user_tag, name='update_user_tag'),
    path('get_organization_tags/<int:org_id>/', views.get_organization_tags, name='get_organization_tags'),
    path('event_details/<int:event_id>/', views.event_details, name='event_details'),
    path('get_owned_organizations/', views.get_owned_organizations, name='get_owned_organizations'),
    path('get_event_attendees/<int:event_id>/', views.get_event_attendees, name='get_event_attendees'),
    path('org_attendance/', views.org_attendance, name='org_attendance'),
    path('get_org_attendance/<int:org_id>/', views.get_org_attendance, name='get_org_attendance'),
    path('export_org_attendance/<int:org_id>/', views.export_org_attendance, name='export_org_attendance'),
    path('get_member_attendance_details/<int:org_id>/<int:member_id>/', views.get_member_attendance_details, name='get_member_attendance_details'),
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
]
