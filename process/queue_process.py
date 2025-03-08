import os
import json
import time
import boto3
import psycopg2
from io import BytesIO
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from botocore.exceptions import NoCredentialsError, BotoCoreError

# AWS Configuration
AWS_REGION = "us-east-2"
S3_BUCKET = "md-media-assets-23"
SECRET_NAME = "rds!cluster-19acf51e-0cab-4b08-b87a-6232c60bed1c"

# Google Drive Configuration
CREDENTIALS_FILE = os.path.expanduser("~/gdrive-service-key.json")
BATCH_SIZE = 10  # Number of files to process per DB query

def get_db_credentials():
    """Retrieves RDS credentials from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=AWS_REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])
    return {
        "user": secret["username"],
        "password": secret["password"],
        "database": secret.get("dbname", "postgres"),
        "host": secret["host"]
    }

def connect_db():
    """Connects to RDS PostgreSQL database."""
    creds = get_db_credentials()
    return psycopg2.connect(
        dbname=creds["database"],
        user=creds["user"],
        password=creds["password"],
        host=creds["host"],
        port=5432
    )

def authenticate_google_drive():
    """Authenticates with Google Drive API using a service account."""
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def stream_to_s3(service, file_id, s3_path):
    """Streams a Google Drive file directly to S3 without saving to disk."""
    try:
        request = service.files().get_media(fileId=file_id)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        
        buffer = BytesIO()
        downloader = MediaIoBaseDownload(buffer, request, chunksize=10485760)  # 10MB chunks
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"⬇️ Downloading {s3_path}... {int(status.progress() * 100)}% complete")

        buffer.seek(0)  # Reset buffer for upload
        s3.upload_fileobj(buffer, S3_BUCKET, s3_path)
        print(f"✅ Uploaded to S3: s3://{S3_BUCKET}/{s3_path}")
        return True
    except (HttpError, NoCredentialsError, BotoCoreError) as e:
        print(f"❌ ERROR: Streaming upload failed for {file_id} - {e}")
        return False

def process_queue():
    """Processes queue: Streams from Google Drive to S3 and updates DB until no files remain."""
    conn = connect_db()
    cursor = conn.cursor()
    service = authenticate_google_drive()

    while True:
        # Fetch files in batches
        cursor.execute("SELECT id, gdrive_id, new_name, path_new FROM media WHERE downloaded = FALSE LIMIT %s", (BATCH_SIZE,))
        files = cursor.fetchall()

        if not files:
            print("✅ All files have been processed. Queue is empty.")
            break  # Exit loop when there are no more files

        for file_id, gdrive_id, new_name, path_new in files:
            s3_path = f"{path_new}/{new_name}"

            # Stream directly to S3
            if not stream_to_s3(service, gdrive_id, s3_path):
                continue  # Skip to next file on failure

            # Update database to mark file as downloaded
            cursor.execute("UPDATE media SET downloaded = TRUE WHERE id = %s", (file_id,))
            conn.commit()
            print(f"✅ Updated DB: {new_name} marked as downloaded.")

        print(f"🔄 Batch of {len(files)} files processed. Checking for more...")

        # Short delay to avoid hammering the database
        time.sleep(2)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    process_queue()