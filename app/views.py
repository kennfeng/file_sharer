from django.shortcuts import render, get_object_or_404
from django.http import Http404, FileResponse
from django.conf import settings
from .models import FileUpload
from .forms import UploadForm
import os

def upload_file(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)

        if form.is_valid():
            file = form.save()
            total_uploads = FileUpload.objects.count()

            # Local storage cleanup
            if total_uploads > 5:
                excess_files = FileUpload.objects.order_by('uploaded_at')[:total_uploads - 5]

                for old_file in excess_files:
                    old_file.file.delete(save = False)
                    old_file.delete()

            # Get the current domain for the download link
            domain = request.get_host()
            return render(request, 'link.html', {'token': file.download_token, 'domain': domain})
    else:
        form = UploadForm()
    return render(request, 'upload.html', {'form': form})

def preview_file(request, token):
    file_obj = get_object_or_404(FileUpload, download_token = token)

    if file_obj.used:
        return render(request, 'used.html')

    return render(request, 'preview.html', {'file': file_obj})

def download_file(request, token):
    file_obj = get_object_or_404(FileUpload, download_token = token)

    if file_obj.used:
        return render(request, 'used.html')
    
    file_obj.used = True
    file_obj.save()

    # Avoids displaying file in browser instead of downloading
    filename = os.path.basename(file_obj.file.name)
    response = FileResponse(file_obj.file.open('rb'))

    # Use filename when downloading
    response['Content-Disposition'] = f'attachment; filename = "{filename}"'

    return response