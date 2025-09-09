from django.test import TestCase
from django.urls import reverse
from .models import FileUpload
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
import uuid

class FileUploadTests(TestCase):
    def test_upload(self):
        test_file = SimpleUploadedFile('test.txt', b'testing upload')
        response = self.client.post(reverse('upload'), {'file': test_file})
        
        # Successful http request
        self.assertEqual(response.status_code, 200)
        # Correct data sent to template
        self.assertIn('token', response.context)

    def test_upload_invalid_form(self):
        response = self.client.post(reverse('upload'), {'file': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please check your file and try again.')

    def test_preview(self):
        test_file = SimpleUploadedFile('test.txt', b'testing preview')
        response = self.client.post(reverse('upload'), {'file': test_file})

        # Generate URL and simulate visit
        token = response.context['token']
        preview_url =  reverse('preview', kwargs = {'token': token})
        response = self.client.get(preview_url)
        
        self.assertEqual(response.status_code, 200)
        # Correct template rendered
        self.assertContains(response, 'File Ready for Download')

    def test_preview_file_not_found(self):
        response = self.client.get(reverse('preview', kwargs={'token': '00000000-0000-0000-0000-000000000000'}))
        self.assertEqual(response.status_code, 404)

    def test_preview_file_used(self):
        test_file = SimpleUploadedFile('test.txt', b'testing used file')
        response = self.client.post(reverse('upload'), {'file': test_file})
        token = response.context['token']
        file_obj = FileUpload.objects.get(download_token=token)
        file_obj.used = True
        file_obj.save()

        preview_url = reverse('preview', kwargs={'token': token})
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link Already Used')

    def test_download(self):
        test_file = SimpleUploadedFile('test.txt', b'testing download')
        response = self.client.post(reverse('upload'), {'file': test_file})

        token = response.context['token']
        download_url = reverse('download', kwargs = {'token': token})
        response = self.client.get(download_url)

        # Successful http request
        self.assertEqual(response.status_code, 200)
        # Assure browser is downloading the file
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

        # Assure file is marked as used
        file_obj = FileUpload.objects.get(download_token = token)
        self.assertTrue(file_obj.used)

    @patch('app.forms.UploadForm.save', side_effect=Exception("DB failure"))
    def test_upload_form_save_exception(self, mock_save):
        test_file = SimpleUploadedFile('fail.txt', b'fail test')
        response = self.client.post(reverse('upload'), {'file': test_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An error occurred while uploading. Please try again.')

    @patch('app.models.FileUpload.delete', side_effect=Exception("Delete failure"))
    def test_upload_file_delete_exception(self, mock_delete):
        # Create an existing file so the delete loop runs
        old_file = FileUpload.objects.create(
            file=SimpleUploadedFile('old.txt', b'old content'),
            download_token=uuid.uuid4()  # <-- use a valid UUID
        )

        test_file = SimpleUploadedFile('fail.txt', b'fail test')
        response = self.client.post(reverse('upload'), {'file': test_file})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An error occurred while uploading. Please try again.')
        self.assertTrue(mock_delete.called)

    def test_upload_large_file(self):
        large_file = SimpleUploadedFile('large.txt', b'a' * (501 * 1024 * 1024))
        response = self.client.post(reverse('upload'), {'file': large_file})
        self.assertContains(response, 'File size exceeds 500 MB limit.')

    def test_upload_unsupported_extension(self):
        unsupported_file = SimpleUploadedFile('test.exe', b'malicious code')
        response = self.client.post(reverse('upload'), {'file': unsupported_file})
        self.assertContains(response, 'Unsupported file type: .exe')

    def test_download_file_not_found(self):
        response = self.client.get(reverse('download', kwargs={'token': '00000000-0000-0000-0000-000000000000'}))
        self.assertEqual(response.status_code, 404)

    def test_download_file_used(self):
        test_file = SimpleUploadedFile('test.txt', b'testing used file for download')
        response = self.client.post(reverse('upload'), {'file': test_file})
        token = response.context['token']
        file_obj = FileUpload.objects.get(download_token=token)
        file_obj.used = True
        file_obj.save()

        download_url = reverse('download', kwargs={'token': token})
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link Already Used')