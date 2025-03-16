#!/bin/bash
# scripts/deploy_service.sh - Deploy file-organizer service

echo "===== Deploying file-organizer service ====="

# Ensure manifest file exists
if [ ! -f "copilot/file-organizer/manifest.yml" ]; then
  echo "Creating service manifest..."
  mkdir -p copilot/file-organizer
  
  cat > copilot/file-organizer/manifest.yml << 'EOF'
# The manifest for the "file-organizer" service.
name: file-organizer
type: Worker Service

# Configuration for your containers and service.
image:
  # Docker build arguments.
  build: Dockerfile

cpu: 256       # Number of CPU units for the task.
memory: 512    # Amount of memory in MiB used by the task.
count: 1       # Number of tasks that should be running in your service.
exec: true     # Enable running commands in your container.

# Network configuration for database access
network:
  vpc:
    placement: private

# Environment variables
variables:                    
  LOG_LEVEL: info
  DB_HOST: "files-1-instance-1.c34g8w4k21dz.us-east-2.rds.amazonaws.com"
  DB_PORT: "5432"
  DB_NAME: "files"
  DB_USER: "postgres"

secrets:
  DB_PASSWORD: "/file-organizer/db/password"  # SSM Parameter Store

# Overrides by environment
environments:
  fo-env:
    count: 1
EOF
fi

# Ensure database access addon exists
if [ ! -f "copilot/file-organizer/addons/database-access.yml" ]; then
  echo "Creating database access addon..."
  mkdir -p copilot/file-organizer/addons
  
  cat > copilot/file-organizer/addons/database-access.yml << 'EOF'
Parameters:
  App:
    Type: String
    Description: Your application's name.
  Env:
    Type: String
    Description: The environment name your service is being deployed to.
  Name:
    Type: String
    Description: The name of the service.

Resources:
  # Security group rule to allow access to RDS
  RDSAccessRule1:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: sg-0fc9d35e72c3206f8
      Description: !Sub Allow PostgreSQL access from ${App}-${Env}-${Name}
      IpProtocol: tcp
      FromPort: 5432
      ToPort: 5432
      SourceSecurityGroupId:
        Fn::ImportValue:
          !Sub ${App}-${Env}-SecurityGroup

  RDSAccessRule2:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: sg-01357db7771992d86
      Description: !Sub Allow PostgreSQL access from ${App}-${Env}-${Name}
      IpProtocol: tcp
      FromPort: 5432
      ToPort: 5432
      SourceSecurityGroupId:
        Fn::ImportValue:
          !Sub ${App}-${Env}-SecurityGroup

  RDSAccessRule3:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: sg-0554ad948de7bc010
      Description: !Sub Allow PostgreSQL access from ${App}-${Env}-${Name}
      IpProtocol: tcp
      FromPort: 5432
      ToPort: 5432
      SourceSecurityGroupId:
        Fn::ImportValue:
          !Sub ${App}-${Env}-SecurityGroup

  # Add egress rule for VPC endpoints
  TaskSecurityGroupEgress:
    Type: AWS::EC2::SecurityGroupEgress
    Properties:
      GroupId:
        Fn::ImportValue:
          !Sub ${App}-${Env}-SecurityGroup
      Description: Allow outbound traffic to RDS
      IpProtocol: tcp
      FromPort: 5432
      ToPort: 5432
      CidrIp: 172.31.48.48/32
EOF
fi

# Ensure DB password parameter exists
echo "Checking if DB password parameter exists..."
if ! aws ssm get-parameter --name "/file-organizer/db/password" --with-decryption > /dev/null 2>&1; then
  echo "Creating DB password parameter..."
  read -sp "Enter database password: " dbpass
  echo
  aws ssm put-parameter --name "/file-organizer/db/password" --value "$dbpass" --type SecureString --overwrite
fi

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
  echo "Dockerfile not found. Creating a basic Dockerfile..."
  
  cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["python", "app.py"]
EOF

  # Create a basic app.py if it doesn't exist
  if [ ! -f "app.py" ]; then
    echo "Creating basic app.py..."
    
    cat > app.py << 'EOF'
import os
import time
import logging
import psycopg2

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("file-organizer")

# Database connection parameters
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def test_db_connection():
    """Test the database connection."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logger.info("Database connection successful!")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def main():
    """Main application loop."""
    logger.info("File Organizer service started")
    
    # Initial DB connection test
    db_connected = test_db_connection()
    
    # Main loop
    try:
        while True:
            logger.info("Working...")
            
            # Retry DB connection if previous attempt failed
            if not db_connected:
                db_connected = test_db_connection()
            
            time.sleep(60)  # Sleep for 1 minute
    except KeyboardInterrupt:
        logger.info("Service stopping due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    
    logger.info("File Organizer service stopped")

if __name__ == "__main__":
    main()
EOF
  fi

  # Create requirements.txt if it doesn't exist
  if [ ! -f "requirements.txt" ]; then
    echo "Creating requirements.txt..."
    
    cat > requirements.txt << 'EOF'
psycopg2-binary==2.9.5
EOF
  fi
fi

# Deploy the service
echo "Deploying file-organizer service to fo-env environment..."
copilot svc deploy --name file-organizer --env fo-env

# Check the deployment status
echo "Checking deployment status..."
sleep 10  # Give it some time to start deployment
copilot svc status --name file-organizer --env fo-env

echo "Deployment initiated. Check deployment progress with:"
echo "  copilot svc status --name file-organizer --env fo-env"
echo "  copilot svc logs --name file-organizer --env fo-env --follow"
