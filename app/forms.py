from django import forms
from .models import FileUpload

class UploadForm(forms.ModelForm):
    class Meta:
        model = FileUpload
        fields = ['file']

    # Max file upload size
    def clean_file(self):
        file = self.cleaned_data.get('file')
        max_size_mb = 500
        
        if file and file.size > max_size_mb * 1024 * 1024:
            raise forms.ValidationError(f'File size exceeds {max_size_mb} MB limit.')
        return file