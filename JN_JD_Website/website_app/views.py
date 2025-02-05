from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .forms import SignInForm

def index(request):
    context = {

    }
    return render(request, 'home.html', context)

def about(request):
    context = {
        
    }
    return render(request, 'index.html', context)

def login(request):
    context = {
        
    }
    return render(request, 'login.html', context)

def sign_in(request):
    if request.method == "POST":
        form = SignInForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)

            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            return redirect('about')
    else:
        form = SignInForm()
    context = {
        'form':form
    }
    return render(request, 'signin.html', context)