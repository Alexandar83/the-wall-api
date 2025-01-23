#!/bin/bash

# Script to ensure the correct run order of the Docker Compose services
# Ensures that migrations are run after the PostgreSQL DB is ready
echo
echo "=== DEV COMPOSE START ==="

# Start the Redis and PostgreSQL services, but skip `wait_for_postgres`
echo "=== STAGE 1 ==="
echo "Starting Redis and PostgreSQL..."
docker compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up --build -d redis postgres
echo

# Wait for the wait_for_postgres service to finish
echo "=== STAGE 2 ==="
echo "Waiting for PostgreSQL..."
echo
docker compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml run --rm wait_for_postgres

# Run migrations locally
echo "=== STAGE 3 ==="
echo "PostgreSQL is ready, running migrations..."
echo
python manage.py makemigrations the_wall_api
python manage.py migrate
echo


# Set up the logs directory
echo "=== STAGE 4 ==="
echo "Migrations complete, setting up logs directory..."
echo

source "$(dirname "$0")/../linux/common_utils.sh"
create_and_setup_logs_directory
return_code=$?
if [[ $return_code -eq 1 ]]; then
    echo "Error: Failed to set up logs directory."
    echo
    exit 1
elif [[ $return_code -eq 11 ]]; then
    echo
    exit 1
fi
echo

# Build the latest app's image
echo "=== STAGE 5 ==="
echo "Logs directory configured, building the Celery services' images..."
echo
docker compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml build celery_beat celery_worker_1
echo

# Start the Celery services
echo "=== STAGE 6 ==="
echo "Celery images built, starting the Celery services..."
echo
docker compose -p the-wall-api-dev -f config/docker/docker-compose-dev.yml up -d celery_beat celery_worker_1 celery_worker_2
echo

echo "=== DEV COMPOSE FINISH ==="
echo