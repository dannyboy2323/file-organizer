import json
import psycopg2
import boto3

# AWS Secrets Manager Configuration
SECRET_NAME = "rds!cluster-19acf51e-0cab-4b08-b87a-6232c60bed1c"
REGION_NAME = "us-east-2"
RDS_WRITER_ENDPOINT = "files-1.cluster-c34g8w4k21dz.us-east-2.rds.amazonaws.com"
RDS_PORT = 5432

def get_db_credentials():
    """Fetches RDS credentials from AWS Secrets Manager."""
    try:
        client = boto3.client(service_name="secretsmanager", region_name=REGION_NAME)
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        return {
            "user": secret["username"],
            "password": secret["password"],
            "database": secret.get("dbname", "postgres"),
        }
    except Exception as e:
        print(f"❌ ERROR: Unable to retrieve RDS credentials - {e}")
        exit(1)

def connect_db():
    """Establishes a connection to PostgreSQL RDS."""
    try:
        creds = get_db_credentials()
        conn = psycopg2.connect(
            dbname=creds["database"],
            user=creds["user"],
            password=creds["password"],
            host=RDS_WRITER_ENDPOINT,
            port=RDS_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"❌ ERROR: Unable to connect to RDS - {e}")
        exit(1)

def initialize_db():
    """Ensures the media table is created with the correct schema."""
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

if __name__ == "__main__":
    initialize_db()
