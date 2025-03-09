
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

AWS Secrets Manager Configuration

REGION_NAME = "us-east-2"
SECRETS_TO_FETCH = [
"rds!cluster-19acf51e-0cab-4b08-b87a-6232c60bed1c",  # RDS Credentials
"file_organizer_s3_bucket",  # S3 Bucket Name
"file_organizer_gdrive_credentials",  # Google Drive API Credentials
"file_organizer_rds_endpoint",  # RDS Endpoint (if not in main secret)
"file_organizer_rds_port",  # RDS Port (if not in main secret)
]

def get_secret(secret_name):
"""Fetches a specific secret from AWS Secrets Manager."""
try:
client = boto3.client(service_name="secretsmanager", region_name=REGION_NAME)
response = client.get_secret_value(SecretId=secret_name)
return json.loads(response["SecretString"])
except (BotoCoreError, KeyError, json.JSONDecodeError) as e:
print(f"❌ ERROR: Unable to retrieve secret '{secret_name}' - {e}")
return None

def fetch_all_secrets():
"""Retrieves all required AWS secrets."""
secrets_data = {}
for secret_name in SECRETS_TO_FETCH:
secret = get_secret(secret_name)
if secret:
secrets_data.update(secret)
return secrets_data

Load all secrets

secrets = fetch_all_secrets()

Extract Secrets

RDS_HOST = secrets.get("host", "files-1.cluster-c34g8w4k21dz.us-east-2.rds.amazonaws.com")
RDS_PORT = secrets.get("port", 5432)
RDS_USER = secrets.get("username", "postgres")
RDS_PASSWORD = secrets.get("password", "")
RDS_DBNAME = secrets.get("dbname", "postgres")
S3_BUCKET_NAME = secrets.get("bucket_name", None)
GOOGLE_DRIVE_CREDENTIALS = secrets.get("file_organizer_gdrive_credentials", None)

Google Drive Configuration

GOOGLE_DRIVE_FOLDER_ID = "1b6zM1oXz_Ewnyp81OnrgQIogrFaBt7SP"
CREDENTIALS_FILE = os.path.expanduser("~/gdrive-service-key.json")

Define MIME types to move (Google Docs, Sheets, Slides)

NON_BINARY_MIME_TYPES = [
"application/vnd.google-apps.document",
"application/vnd.google-apps.spreadsheet",
"application/vnd.google-apps.presentation"
]

def connect_db():
"""Establishes a connection to PostgreSQL RDS using AWS Secrets Manager."""
try:
conn = psycopg2.connect(
dbname=RDS_DBNAME,
user=RDS_USER,
password=RDS_PASSWORD,
host=RDS_HOST,
port=RDS_PORT
)
return conn
except psycopg2.Error as e:
print(f"❌ ERROR: Unable to connect to RDS - {e}")
exit(1)

def initialize_db():
"""Ensures the 'media' table exists with the correct schema."""
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
processed BOOLEAN DEFAULT FALSE,
file_size INTEGER,
length REAL,
date_created TEXT,
date_edited TEXT,
people TEXT,
segments TEXT,
tags TEXT,
summary TEXT,
trailer TEXT,
s3_path TEXT,
new_name TEXT,
added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()
cursor.close()
conn.close()
print("✅ Database initialized successfully.")

def authenticate_google_drive():
"""Authenticates with Google Drive API using credentials from AWS Secrets Manager."""
try:
with open(CREDENTIALS_FILE, "w") as f:
f.write(json.dumps(GOOGLE_DRIVE_CREDENTIALS))

creds = service_account.Credentials.from_service_account_file(  
        CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/drive"]  
    )  
    return build("drive", "v3", credentials=creds)  
except Exception as e:  
    print(f"❌ ERROR: Google Drive authentication failed - {e}")  
    exit(1)

def move_drive_file(service, file_id, destination_folder_id):
"""Moves a file in Google Drive to a different folder."""
try:
file = service.files().get(fileId=file_id, fields="parents").execute()
previous_parents = ",".join(file.get("parents"))
service.files().update(
fileId=file_id, addParents=destination_folder_id, removeParents=previous_parents, fields="id, parents"
).execute()
print(f"✅ Moved file {file_id} to {destination_folder_id}")
except HttpError as e:
print(f"❌ ERROR: Failed to move file {file_id} - {e}")

def process_files(service):
"""Processes files, detects duplicates, and moves them appropriately."""
while True:
print("🔍 Fetching file list from Google Drive...")
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
            for file in file_list[1:]:  
                print(f"📂 Moving duplicate {file['name']} to 'dupes' folder")  
                move_drive_file(service, file["id"], "_watched/dupes/")  

        file = file_list[0]  
        file_id, original_name, mime_type = file["id"], file["name"], file["mimeType"]  

        if mime_type in NON_BINARY_MIME_TYPES:  
            print(f"📂 Moving {original_name} to 'documents' folder")  
            move_drive_file(service, file_id, "_watched/documents/")  
            continue  

        cursor.execute("""  
            INSERT INTO media (  
                original_path, original_name, gdrive_id, uuid, type, extension,  
                downloaded, processed, file_size, length, date_created, date_edited,   
                people, segments, tags, summary, trailer, s3_path, new_name  
            )  
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  
            ON CONFLICT (gdrive_id) DO NOTHING  
        """, (original_name, original_name, file_id, str(uuid.uuid4()), "image",  
            os.path.splitext(original_name)[-1][1:], False, False, file.get("size", None),  
            None, None, None, None, None, None, None, None, None, None))  
        conn.commit()  

        move_drive_file(service, file_id, "_watched/download/")  

    conn.close()  
    time.sleep(5)

initialize_db()
service = authenticate_google_drive()
process_files(service)

