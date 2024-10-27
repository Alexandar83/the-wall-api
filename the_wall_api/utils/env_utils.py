import os
import sys

ACTIVE_TESTING = True if 'test' in sys.argv else False
PROJECT_MODE = os.getenv('PROJECT_MODE', 'dev')


def configure_connections_settings(DATABASES=None) -> dict:
    result = {}

    REDIS_URL = os.getenv('REDIS_URL')

    REDIS_DB_NUMBER = os.getenv('REDIS_DB_NUMBER', '0')
    REDIS_DB_NUMBER_CELERY = os.getenv('REDIS_DB_NUMBER_CELERY', '2')

    STARTED_FROM_CELERY_SERVICE = os.getenv('STARTED_FROM_CELERY_SERVICE', 'False') == 'True'

    # --Note 1--
    # On dev. the app is not containerized:
    # 'redis' and 'postgres' are not properly resolved locally from the Django dev server and
    # localhost is not accessible in the Celery services
    if PROJECT_MODE == 'dev' and STARTED_FROM_CELERY_SERVICE and DATABASES:
        DATABASES['default']['HOST'] = 'postgres'

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
            # See --Note 1--
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
