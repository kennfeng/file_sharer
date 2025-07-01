from django.urls import path
from django.http import HttpResponse
from . import views

def public_home(request):
    return HttpResponse("Use your one-time download links.")

urlpatterns = [
    path('', public_home, name = 'public_home'),
    path('preview/<uuid:token>/', views.preview_file, name = 'preview'),
    path('download/<uuid:token>/', views.download_file, name = 'download'),
]
