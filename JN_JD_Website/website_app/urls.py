from django.urls import path
from . import views  # Import your app's views

app_name = 'website_app'  # Optional: Namespacing for reverse URL lookups

urlpatterns = [
    path('', views.index, name='index'),
]