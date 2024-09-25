#!/bin/bash

# Script to ensure that postgres is running before migrations are run

# Start Docker Compose services, but skip `wait_for_postgres`
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up --build -d redis postgres

# Wait for the wait_for_postgres service to finish
echo "Waiting for PostgreSQL to be ready..."
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml run --rm wait_for_postgres

# Run migrations locally
echo "PostgreSQL is ready, running migrations..."
python manage.py migrate