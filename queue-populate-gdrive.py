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

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = "1b6zM1oXz_Ewnyp81OnrgQIogrFaBt7SP"
CREDENTIALS_FILE = os.path.expanduser("~/gdrive-service-key.json")

# AWS RDS Configuration
SECRET_NAME = "rds!cluster-19acf51e-0cab-4b08-b87a-6232c60bed1c"
REGION_NAME = "us-east-2"
RDS_WRITER_ENDPOINT = "files-1.cluster-c34g8w4k21dz.us-east-2.rds.amazonaws.com"
RDS_PORT = 5432

# Define MIME types to move (Google Docs, Sheets, Slides)
NON_BINARY_MIME_TYPES = [
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation"
]

def get_db_credentials():
    """ Retrieves RDS credentials from AWS Secrets Manager with error handling. """
    try:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=REGION_NAME)
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        return {
            "user": secret["username"],
            "password": secret["password"],
            "database": secret.get("dbname", "postgres"),
        }
    except (BotoCoreError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR: Unable to retrieve RDS credentials - {e}")
        exit(1)

def connect_db():
    """ Establishes a connection to PostgreSQL RDS. """
    try:
        creds = get_db_credentials()
        return psycopg2.connect(
            dbname=creds["database"],
            user=creds["user"],
            password=creds["password"],
            host=RDS_WRITER_ENDPOINT,
            port=RDS_PORT
        )
    except psycopg2.Error as e:
        print(f"ERROR: Unable to connect to RDS - {e}")
        exit(1)

def initialize_db():
    """ Ensures the 'media' table exists and contains the necessary columns. """
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

def authenticate_google_drive():
    """ Authenticates with Google Drive API using a service account. """
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"ERROR: Google Drive authentication failed - {e}")
        exit(1)

def move_drive_file(service, file_id, destination_folder_id):
    """ Moves a file in Google Drive to a different folder. """
    try:
        file = service.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))
        service.files().update(fileId=file_id, addParents=destination_folder_id, removeParents=previous_parents, fields="id, parents").execute()
        print(f"Moved file {file_id} to {destination_folder_id}")
    except HttpError as e:
        print(f"ERROR: Failed to move file {file_id} - {e}")

def process_files(service):
    """ Processes files, detects duplicates, and moves them appropriately. """
    while True:
        print("Fetching file list from Google Drive...")
        files = service.files().list(
            q=f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, mimeType, size)"
        ).execute().get("files", [])

        if not files:
            print("✅ All files in `_watched/` have been processed. Exiting loop.")
            break

        conn = connect_db()
        cursor = conn.cursor()
        file_tracker = defaultdict(list)

        for file in files:
            file_tracker[(file["name"], file.get("size", 0), file["mimeType"])].append(file)

        for key, file_list in file_tracker.items():
            if len(file_list) > 1:
                # Move all duplicates except one to `_watched/dupes/`
                for file in file_list[1:]:
                    print(f"Moving duplicate {file['name']} to 'dupes' folder")
                    move_drive_file(service, file["id"], "_watched/dupes/")

            file = file_list[0]
            file_id, original_name, mime_type = file["id"], file["name"], file["mimeType"]

            # Move non-binary files (Docs, Sheets, Slides) to `documents/`
            if mime_type in NON_BINARY_MIME_TYPES:
                print(f"Moving {original_name} to 'documents' folder")
                move_drive_file(service, file_id, "_watched/documents/")
                continue

            # Mark file as queued for download
            cursor.execute("""
                INSERT INTO media (original_path, original_name, gdrive_id, uuid, type, extension, downloaded)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (gdrive_id) DO NOTHING
            """, (original_name, original_name, file_id, str(uuid.uuid4()), "image", os.path.splitext(original_name)[-1][1:], False))
            conn.commit()

            # Move file to `_watched/download/`
            move_drive_file(service, file_id, "_watched/download/")

        conn.close()

        # Print summary
        print("\n🔹 **Google Drive Processing Summary:**")
        print(f"📂 Total Files Processed: {len(files)}")
        print(f"🛑 Duplicates moved to `dupes/`: {sum(len(lst) - 1 for lst in file_tracker.values() if len(lst) > 1)}")
        print(f"📄 Non-binary files moved to `documents/`: {sum(1 for lst in file_tracker.values() if lst[0]['mimeType'] in NON_BINARY_MIME_TYPES)}")
        print(f"✅ Files moved to `download/` for processing: {sum(1 for lst in file_tracker.values() if lst[0]['mimeType'] not in NON_BINARY_MIME_TYPES)}")

        time.sleep(5)  # Small delay before checking again

# Initialize DB and process files
initialize_db()
service = authenticate_google_drive()
process_files(service)
