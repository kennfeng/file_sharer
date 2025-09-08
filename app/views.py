from django.shortcuts import render, get_object_or_404
from django.http import Http404, FileResponse, HttpResponseServerError
from django.conf import settings
from django.core.exceptions import ValidationError
from .models import FileUpload
from .forms import UploadForm
import os
import logging

logger = logging.getLogger(__name__)

from ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='10/m', block=True) # Limit to 10 uploads per minute per IP
def upload_file(request):
    if request.method == 'POST':
        try:
            form = UploadForm(request.POST, request.FILES)

            if form.is_valid():
                # Delete all existing files before saving the new one
                existing_files = FileUpload.objects.all()
                logger.info(f"Found {existing_files.count()} existing files to delete")
                
                for old_file in existing_files:
                    try:
                        logger.info(f"Deleting file: {old_file.file.name} (ID: {old_file.id})")
                        # Delete the file from storage
                        old_file.file.delete(save=False)
                        old_file.delete()
                        logger.info(f"Successfully deleted file ID: {old_file.id}")
                    except Exception as e:
                        logger.error(f"Error deleting old file {old_file.id}: {str(e)}")
                        # Continue with other files even if one fails
                        old_file.delete()  # Delete the database record anyway

                # Now save the new file
                try:
                    file = form.save()
                    logger.info(f"File saved: {file.file.name}")
                except Exception as e:
                    logger.error(f"form.save() failed: {e}", exc_info=True)
                    raise

                # Get the current domain for the download link
                protocol = 'https' if request.is_secure() else 'http'
                domain = f"{protocol}://{request.get_host()}"
                return render(request, 'link.html', {'token': file.download_token, 'domain': domain})
            else:
                logger.warning(f"Form validation failed: {form.errors}")
                return render(request, 'upload.html', {'form': form, 'error': 'Please check your file and try again.'})
                
        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            return render(request, 'upload.html', {'form': UploadForm(), 'error': 'An error occurred while uploading. Please try again.'})
    else:
        form = UploadForm()
    return render(request, 'upload.html', {'form': form})

def preview_file(request, token):
    try:
        file_obj = get_object_or_404(FileUpload, download_token = token)

        if file_obj.used:
            return render(request, 'used.html')

        return render(request, 'preview.html', {'file': file_obj})
    except Exception as e:
        logger.error(f"Preview error for token {token}: {str(e)}", exc_info=True)
        raise Http404("File not found")

def download_file(request, token):
    try:
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
    except Exception as e:
        logger.error(f"Download error for token {token}: {str(e)}", exc_info=True)
        raise Http404("File not found")