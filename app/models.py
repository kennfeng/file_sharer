from django.db import models
import uuid

class FileUpload(models.Model):
    # Directory
    file = models.FileField(upload_to = 'uploads/')
    download_token = models.UUIDField(default = uuid.uuid4, unique = True)
    used = models.BooleanField(default = False)
    uploaded_at = models.DateTimeField(auto_now_add = True)