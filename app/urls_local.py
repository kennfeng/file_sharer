from django.urls import path
from . import views

urlpatterns = [
    # Upload only available on localhost
    path('', views.upload_file, name = 'upload'),
    path('preview/<uuid:token>/', views.preview_file, name = 'preview'),
    path('download/<uuid:token>/', views.download_file, name = 'download'),
]
