#!/bin/bash
set -eo pipefail

APP_NAME="file-organizer"
ENVIRONMENTS=("test" "prod")

# Initialize application
copilot app init "$APP_NAME"

# Create environments
copilot env init --name test --default-config
copilot env init --name prod --prod --default-config

# Deploy test environment
copilot env deploy --name test
copilot svc deploy --name api --env test
copilot svc deploy --name worker --env test

# Run test validation
copilot svc exec --name api --env test --command "python manage.py test"

# Deploy production environment
copilot env deploy --name prod --source test
copilot svc deploy --name api --env prod
copilot svc deploy --name worker --env prod

# Enable production protections
copilot env update --name prod \
  --restrict-ecr-deletes \
  --restrict-routes \
  --enable-dns-verification

# Set up monitoring
copilot observability init \
  --alarms \
  --dashboard \
  --trace

echo "Deployment complete. Production environment protected and monitored."
