import os
import json
import time
import boto3
import psycopg2
import uuid
from collections import defaultdict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from botocore.exceptions import BotoCoreError

AWS_REGION = "us-east-2"

def get_secret(secret_id):
    """Retrieve a secret from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=AWS_REGION)
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])

def get_db_credentials():
    """Retrieves RDS credentials from AWS Secrets Manager."""
    return get_secret("file_organizer_rds_secret")

def authenticate_google_drive():
    """Authenticates with Google Drive API using service account credentials from AWS Secrets Manager."""
    creds_data = get_secret("gdrive-service-key")
    creds = service_account.Credentials.from_service_account_info(
        creds_data, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def connect_db():
    """Connects to PostgreSQL RDS."""
    creds = get_db_credentials()
    return psycopg2.connect(
        dbname=creds.get("dbname", "postgres"),
        user=creds["username"],
        password=creds["password"],
        host=creds["host"],
        port=5432
    )

def initialize_db():
    """Ensures the 'media' table exists."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id SERIAL PRIMARY KEY,
            original_path TEXT UNIQUE,
            original_name TEXT,
            gdrive_id TEXT UNIQUE,
            uuid TEXT,
            type TEXT,
            extension TEXT,
            downloaded BOOLEAN DEFAULT FALSE,
            added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def process_files(service):
    """Processes files, detects duplicates, and moves them appropriately."""
    gdrive_folder_id = get_secret("file_organizer_gdrive_folder_id")

    while True:
        print("Fetching file list from Google Drive...")
        files = service.files().list(
            q=f"'{gdrive_folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, size)"
        ).execute().get("files", [])

        if not files:
            print("✅ All files in `_watched/` have been processed. Exiting loop.")
            break

        conn = connect_db()
        cursor = conn.cursor()

        for file in files:
            cursor.execute("""
                INSERT INTO media (original_path, original_name, gdrive_id, uuid, type, extension, downloaded)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (gdrive_id) DO NOTHING
            """, (file["name"], file["name"], file["id"], str(uuid.uuid4()), "image", os.path.splitext(file["name"])[-1][1:], False))
            conn.commit()

        conn.close()
        print(f"✅ {len(files)} files processed. Checking again in 5 seconds.")
        time.sleep(5)

initialize_db()
service = authenticate_google_drive()
process_files(service)
