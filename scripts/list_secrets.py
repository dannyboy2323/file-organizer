import json
import logging
import boto3

# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------
REGION_NAME = "us-east-2"
OUTPUT_FILE = "aws_secrets_config.json"

# ------------------------------------------------------------------------------
# AWS Secrets Retrieval
# ------------------------------------------------------------------------------
def list_all_secrets():
    """
    Lists all secrets stored in AWS Secrets Manager and retrieves their values.
    Also determines the data type and provides an example value.
    """
    client = boto3.client("secretsmanager", region_name=REGION_NAME)
    secrets_list = {}

    try:
        # Fetch all secrets
        paginator = client.get_paginator("list_secrets")
        for page in paginator.paginate():
            for secret in page.get("SecretList", []):
                secret_name = secret.get("Name")

                try:
                    # Retrieve secret value
                    secret_value_resp = client.get_secret_value(SecretId=secret_name)
                    secret_value = secret_value_resp.get("SecretString")

                    # Determine data type and example
                    secret_data = parse_secret_value(secret_value)

                    # Store in dictionary
                    secrets_list[secret_name] = secret_data

                    logging.info(f"✅ Retrieved secret: {secret_name}")
                
                except Exception as e:
                    logging.error(f"❌ Failed to retrieve secret '{secret_name}': {e}")

    except Exception as e:
        logging.error(f"❌ Error listing AWS Secrets: {e}")

    return secrets_list

# ------------------------------------------------------------------------------
# Secret Parsing Logic
# ------------------------------------------------------------------------------
def parse_secret_value(secret_value):
    """
    Determines if the secret is a JSON object or a simple string.
    Extracts type and provides an example value.
    """
    if not secret_value:
        return {"type": "unknown", "example": "N/A"}

    try:
        # Try parsing as JSON
        parsed_value = json.loads(secret_value)
        if isinstance(parsed_value, dict):
            return {
                "type": "json",
                "example": json.dumps(parsed_value, indent=2)[:300]  # Show first 300 chars
            }
        elif isinstance(parsed_value, list):
            return {
                "type": "list",
                "example": json.dumps(parsed_value[:5], indent=2)  # Show first 5 elements
            }
    except json.JSONDecodeError:
        pass

    # If not JSON, treat as a plain string
    return {"type": "string", "example": secret_value[:100]}  # Show first 100 chars

# ------------------------------------------------------------------------------
# Save to JSON File
# ------------------------------------------------------------------------------
def save_to_json(data, filename):
    """
    Saves the secrets dictionary to a JSON file.
    """
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        logging.info(f"✅ Secrets saved to {filename}")
    except Exception as e:
        logging.error(f"❌ Failed to write to {filename}: {e}")

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("🚀 Retrieving AWS Secrets...")
    secrets_data = list_all_secrets()
    save_to_json(secrets_data, OUTPUT_FILE)
    logging.info("✅ AWS Secrets retrieval completed.")