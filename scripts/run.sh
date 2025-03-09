#!/bin/bash

# Build the Docker images
docker compose build

# Start the services in the background
docker compose up -d

# Check running containers
docker ps

# View logs for both services
docker compose logs -f process &
docker compose logs -f populate &
