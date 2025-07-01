from django.test import TestCase
from django.urls import reverse
from .models import FileUpload
from django.core.files.uploadedfile import SimpleUploadedFile

class FileUploadTests(TestCase):
    def test_upload(self):
        test_file = SimpleUploadedFile('test.txt', b'testing upload')
        response = self.client.post(reverse('upload'), {'file': test_file})
        
        # Successful http request
        self.assertEqual(response.status_code, 200)
        # Correct data sent to template
        self.assertIn('token', response.context)

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