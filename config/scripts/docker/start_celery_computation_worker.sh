#!/bin/bash

# Base Celery command
celery_command="celery -A config worker --loglevel=info --queues=concurrent_tasks"

# If multiprocessing mode, use explicit concurrency config
if [[ "$CONCURRENT_SIMULATION_MODE" == *"multiprocessing"* ]]; then
  celery_command="$celery_command --pool=threads --concurrency=4"
fi

# Execute the final Celery command
exec $celery_command
