# Simple script to wait for PostgreSQL, before starting the Django
# app and running the migrations.
# Avoids introduction of dependencies in Dockerfile.

from socket import create_connection, error as socket_error
from time import time, sleep
import os


def wait_for_postgres(host, port, timeout=60):
    start_time = time()
    while True:
        try:
            with create_connection((host, port), timeout=2):
                print('PostgreSQL is ready!')
                return True
        except (OSError, socket_error):
            time_passed = time() - start_time
            if time_passed >= timeout:
                print('Error: Timeout while waiting for PostgreSQL')
                return False
            print('Waiting for PostgreSQL...')
            sleep(2)


if __name__ == '__main__':
    postgres_host = os.getenv('DB_HOST', 'postgres')
    postgres_port = int(os.getenv('DB_PORT', 5432))

    if not wait_for_postgres(postgres_host, postgres_port):
        exit(1)
