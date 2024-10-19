# Simple script to wait for the Celery worker to be completely initialized,
# before starting Celery beat

from subprocess import CalledProcessError, run
from time import time, sleep


def wait_for_celery_worker(timeout=60):
    start_time = time()
    while True:
        try:
            result = run(
                ['celery', '-A', 'config', 'status'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print('Celery Worker is ready!')
                return True
            else:
                print('Waiting for Celery worker initialization...')
        except CalledProcessError as prcss_err:
            print(f'Error running Celery status check: {prcss_err}')

        time_passed = time() - start_time
        if time_passed >= timeout:
            print('Error: Timeout while waiting for Celery Worker')
            return False
        sleep(2)


if __name__ == '__main__':
    if not wait_for_celery_worker():
        exit(1)
