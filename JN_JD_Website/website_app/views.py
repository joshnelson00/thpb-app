from django.http import HttpResponse
from django.shortcuts import render  # For rendering templates


def index(request):
    context = {

    }
    return render(request, 'index.html', context)

def about(request):
    context = {
        
    }
    return render(request, 'index.html', context)