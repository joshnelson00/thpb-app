from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.sign_in, name='signin'),
    path('createaccount/', views.create_account, name='createaccount'),  # Corrected view name to match
    path('home/', views.home, name='home'),
    path('logout/', LogoutView.as_view(next_page='signin'), name='logout'),
]
