import os
import sys

ACTIVE_TESTING = True if 'test' in sys.argv else False
PROJECT_MODE = os.getenv('PROJECT_MODE', 'dev')


def configure_redis_url_and_celery_settings() -> dict:
    result = {}

    REDIS_URL = os.getenv('REDIS_URL')

    REDIS_DB_NUMBER = os.getenv('REDIS_DB_NUMBER', '0')
    REDIS_DB_NUMBER_CELERY = os.getenv('REDIS_DB_NUMBER_CELERY', '2')

    STARTED_FROM_CELERY_SERVICE = os.getenv('STARTED_FROM_CELERY_SERVICE', 'False') == 'True'

    if REDIS_URL is not None:
        # Inject the password in the url for prod
        if PROJECT_MODE == 'prod_v1':
            REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
            REDIS_URL = REDIS_URL.replace('REDIS_PASSWORD', REDIS_PASSWORD)
        elif PROJECT_MODE == 'prod_v2':
            REDIS_PASSWORD = open(os.environ['REDIS_PASSWORD_FILE']).read().strip()
            REDIS_URL = REDIS_URL.replace('REDIS_PASSWORD', REDIS_PASSWORD)

        # === Celery Configuration ===

        # Ensure separate Redis DB for in-memory-caching and Celery
        CELERY_BROKER_URL = REDIS_URL.replace('REDIS_DB_NUMBER', REDIS_DB_NUMBER_CELERY)

        if PROJECT_MODE == 'dev' and STARTED_FROM_CELERY_SERVICE:
            # On dev. the app is not containerized:
            # 'redis' is not properly resolved locally from the Django dev server and
            # localhost is not accessible in the Celery services
            CELERY_BROKER_URL = CELERY_BROKER_URL.replace('localhost', 'redis')
        # Temporary store the task results for evaluations (testing)
        CELERY_RESULT_BACKEND = CELERY_BROKER_URL

        # === Celery Configuration end ===

        if not ACTIVE_TESTING:
            REDIS_URL = REDIS_URL.replace('REDIS_DB_NUMBER', REDIS_DB_NUMBER)
        else:
            # Use a separate Redis DB for testing
            REDIS_URL = REDIS_URL.replace('REDIS_DB_NUMBER', '1')

        result['REDIS_URL'] = REDIS_URL
        result['CELERY_BROKER_URL'] = CELERY_BROKER_URL
        result['CELERY_RESULT_BACKEND'] = CELERY_RESULT_BACKEND

    result['CELERY_RESULT_EXPIRES'] = '600'

    return result


def configure_env_logging() -> dict:
    result = {}

    LOGS_DIR = os.getenv('LOGS_DIR', 'logs')                                                # Parent logs folder
    result['LOGS_DIR'] = LOGS_DIR

    BUILD_SIM_LOGS_DIR = os.path.join(LOGS_DIR, 'build_simulations')                        # Construction simulation logs
    result['BUILD_SIM_LOGS_DIR'] = BUILD_SIM_LOGS_DIR

    BUILD_SIM_LOGS_ARCHIVE_DIR = os.path.join(BUILD_SIM_LOGS_DIR, 'archive')                # Construction simulation logs archive
    result['BUILD_SIM_LOGS_ARCHIVE_DIR'] = BUILD_SIM_LOGS_ARCHIVE_DIR

    BUILD_SIM_LOGS_RETENTION_DAYS = int(os.getenv('BUILD_SIM_LOGS_RETENTION_DAYS', 1))      # Days of logs retention
    result['BUILD_SIM_LOGS_RETENTION_DAYS'] = BUILD_SIM_LOGS_RETENTION_DAYS

    BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS = int(                                            # Days of logs archive retention
        os.getenv('BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS', 7)
    )
    result['BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS'] = BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS

    return result
