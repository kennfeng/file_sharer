from django import forms
from .models import FileUpload

ALLOWED_EXTENSIONS = [
    'txt', 'pdf', 'jpg', 'jpeg', 'png',
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wav'
]

class UploadForm(forms.ModelForm):
    class Meta:
        model = FileUpload
        fields = ['file']

    def clean_file(self):
        file = self.cleaned_data.get('file')
        max_size_mb = 500

        if file:
            # 1. Check size
            if file.size > max_size_mb * 1024 * 1024:
                raise forms.ValidationError(f'File size exceeds {max_size_mb} MB limit.')

            # 2. Check file extension
            ext = file.name.split('.')[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise forms.ValidationError(f'Unsupported file type: .{ext}')

        return file
