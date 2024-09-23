#!/bin/bash

# Start Docker Compose services
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up --build -d

# Wait for the wait_for_postgres service to finish
echo "Waiting for PostgreSQL to be ready..."
docker-compose -f docker-compose-dev.yml run --rm wait_for_postgres

# Run migrations locally
echo "PostgreSQL is ready, running migrations..."
python manage.py migrate