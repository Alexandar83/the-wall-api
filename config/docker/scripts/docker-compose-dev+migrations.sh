#!/bin/bash

# Script to ensure the correct run order of the Docker Compose services
# Enusres that migrations are run after the PostgreSQL DB is ready
echo
echo "=== DEV COMPOSE START ==="

# Start the Redis and PostgreSQL services, but skip `wait_for_postgres`
echo "=== STAGE 1 ==="
echo "Starting Redis and PostgreSQL..."
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up --build -d redis postgres
echo

# Wait for the wait_for_postgres service to finish
echo "=== STAGE 2 ==="
echo "Waiting for PostgreSQL to be ready..."
echo
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml run --rm wait_for_postgres

# Run migrations locally
echo "=== STAGE 3 ==="
echo "PostgreSQL is ready, running migrations..."
echo
python manage.py migrate
echo

# Build the latest app's image
echo "=== STAGE 4 ==="
echo "Migrations ready, building the Celery worker/beat image with the latest app code..."
echo
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml build celery_worker --no-cache
echo

# Start the Celery worker service
echo "=== STAGE 5 ==="
echo "Build ready, starting the Celery worker service..."
echo
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up -d celery_worker
echo

# Wait for the wait_for_celery_worker service to finish
echo "=== STAGE 6 ==="
echo "Waiting for the Celery worker to start..."
echo
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml run --rm wait_for_celery_worker

# Start the Celery beat service, after the app's image build is finished
echo "=== STAGE 7 ==="
echo "The Celery worker is ready, starting the Celery beat service..."
echo
docker-compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up -d celery_beat
echo

echo "=== DEV COMPOSE FINISH ==="
echo