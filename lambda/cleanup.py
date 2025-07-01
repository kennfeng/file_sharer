import boto3, os
from datetime import datetime, timezone, timedelta

s3 = boto3.client('s3')
BUCKET_NAME = os.getenv('BUCKET_NAME')

# Max file age
MAX_FILE_AGE_MINS = 10

def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    paginator = s3.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket = BUCKET_NAME):
        # Skip no content pages
        if 'Contents' not in page:
            print('Bucket is empty.')
            continue

        for obj in page['Contents']:
            last_modified = obj['LastModified']
            age = now - last_modified
            
            if age > timedelta(minutes = MAX_FILE_AGE_MINS):
                print(f"Deleting {obj['Key']} (age {age.seconds // 60} minutes)")
                s3.delete_object(Bucket = BUCKET_NAME, Key = obj['Key'])
