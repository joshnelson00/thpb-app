from django.urls import path
from . import views
from .views import *

urlpatterns = [
    path('', views.index, name='about'),
    path('login/', views.login, name='login'),
    path('signin/', views.sign_in, name='signin'),
]