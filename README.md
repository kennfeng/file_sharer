# File Sharer

A Django-based file sharing application that provides one-time download links. Users can upload files and get secure, single-use download links that expire after one download.

## Features

- Upload files with a 50MB size limit
- Generate secure one-time download links
- Automatic cleanup of old files (keeps only the 5 most recent)
- Support for both local file storage and AWS S3