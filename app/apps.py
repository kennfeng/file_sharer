from django.apps import AppConfig
from django.conf import settings
import os

class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        # Create uploads directory if it doesn't exist
        uploads_dir = settings.MEDIA_ROOT
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir, exist_ok=True)