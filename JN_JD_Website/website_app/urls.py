from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.sign_in, name='signin'),
    path('createaccount/', views.create_account, name='createaccount'),  # Corrected view name to match
    path('home/', views.home, name='home'),
    path('logout/', LogoutView.as_view(next_page='signin'), name='logout'),
    path('editgroups/', views.edit_groups, name='editgroups'),
    path('editevent/', views.edit_event, name='editevent'),
    path('viewevents/', views.view_events, name='viewevents'),
]
