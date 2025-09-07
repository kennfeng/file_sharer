from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_file, name = 'upload'),
    path('preview/<uuid:token>/', views.preview_file, name = 'preview'),
    path('download/<uuid:token>/', views.download_file, name = 'download'),
]
