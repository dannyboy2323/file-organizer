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

def process_queue():
    """Fetches and processes media records from the database."""
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM media WHERE downloaded = FALSE LIMIT 10;")
    records = cursor.fetchall()

    if not records:
        print("✅ No pending media files to process.")
    else:
        for record in records:
            print(f"📂 Processing media file: {record}")
            
            # Mark file as downloaded
            cursor.execute("UPDATE media SET downloaded = TRUE WHERE id = %s;", (record[0],))
            conn.commit()

    cursor.close()
    conn.close()
    print("✅ Queue processing complete.")

if __name__ == "__main__":
    process_queue()
