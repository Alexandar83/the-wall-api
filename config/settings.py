"""
Django settings for config project.

Generated by 'django-admin startproject' using Django 5.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from the_wall_api.utils.env_utils import ACTIVE_TESTING, configure_redis_url_and_celery_settings, PROJECT_MODE  # noqa: F401

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

if PROJECT_MODE == 'dev':
    # No env. settings are injected in the app from docker-compose

    # App. DEV env. settings
    load_dotenv(dotenv_path=BASE_DIR / 'config' / 'envs' / 'dev' / 'the_wall_api_dev.env')
    # PostgreSQL DEV env. settings
    load_dotenv(dotenv_path=BASE_DIR / 'config' / 'envs' / 'dev' / 'postgres_dev.env', override=True)

SECRET_KEY = 'django-insecure-*x!p!3#xxluj9i+v6anb!laycbax0rbkefg7$wf06xj2-my63f'

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# === Database configuration ===
if PROJECT_MODE in ['dev', 'prod_v1']:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE'),
            'NAME': os.getenv('POSTGRES_DB'),
            'USER': os.getenv('POSTGRES_USER'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
        }
    }
elif PROJECT_MODE == 'prod_v2':
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE'),
            'NAME': open(os.environ['POSTGRES_DB_FILE']).read().strip(),
            'USER': open(os.environ['POSTGRES_USER_FILE']).read().strip(),
            'PASSWORD': open(os.environ['POSTGRES_PASSWORD_FILE']).read().strip(),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
        }
    }

# === Database configuration end ===

# Verbosity of unit tests
# ERROR - only log errors
# FAILED - only log failed tests
# PASSED - only log passed tests
# ALL - log all tests
# NO-LOGGING - disable logging
# SUMMARY - only log tests summary
TEST_LOGGING_LEVEL = os.getenv('TEST_LOGGING_LEVEL', 'NO-LOGGING')

# === Redis Configuration ===

redis_url_and_celery_settings = configure_redis_url_and_celery_settings()

REDIS_URL = redis_url_and_celery_settings['REDIS_URL']
REDIS_CACHE_TRANSIENT_DATA_TIMEOUT = int(os.getenv('REDIS_CACHE_TRANSIENT_DATA_TIMEOUT', 60 * 60 * 24 * 7))
REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 2))
REDIS_SOCKET_TIMEOUT = int(os.getenv('REDIS_SOCKET_TIMEOUT', 2))

# === Celery Configuration ===
CELERY_BROKER_URL = redis_url_and_celery_settings['CELERY_BROKER_URL']
CELERY_RESULT_BACKEND = redis_url_and_celery_settings['CELERY_RESULT_BACKEND']
CELERY_RESULT_EXPIRES = int(redis_url_and_celery_settings['CELERY_RESULT_EXPIRES'])

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
            'SOCKET_CONNECT_TIMEOUT': REDIS_SOCKET_CONNECT_TIMEOUT,
            'SOCKET_TIMEOUT': REDIS_SOCKET_TIMEOUT,
        },
        'TIMEOUT': None
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# === Redis Configuration end ===

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'the_wall_api',
    'drf_spectacular'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'The Wall API',
    'DESCRIPTION': 'Wall construction tracker.',
    'VERSION': '',  # Set your API version here
    'SERVE_INCLUDE_SCHEMA': False,
}

APPEND_SLASH = True

TEST_RUNNER = 'the_wall_api.tests.test_utils.CustomTestRunner'

# === Filesystem configuration ===
# General
WALL_CONFIG_PATH = os.getenv('WALL_CONFIG_PATH', 'config/wall_config.json')             # Location of the wall profile configuration

# Construction simulation logs
LOGS_DIR = os.getenv('LOGS_DIR', 'logs')                                                # Parent logs folder
os.makedirs(LOGS_DIR, exist_ok=True)

BUILD_SIM_LOGS_DIR = os.path.join(LOGS_DIR, 'build_simulations')                        # Construction simulation logs
os.makedirs(BUILD_SIM_LOGS_DIR, exist_ok=True)

BUILD_SIM_LOGS_ARCHIVE_DIR = os.path.join(BUILD_SIM_LOGS_DIR, 'archive')                # Construction simulation logs archive
os.makedirs(BUILD_SIM_LOGS_ARCHIVE_DIR, exist_ok=True)

BUILD_SIM_LOGS_RETENTION_DAYS = int(os.getenv('BUILD_SIM_LOGS_RETENTION_DAYS', 1))      # Days of logs retention
BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS = int(                                            # Days of logs archive retention
    os.getenv('BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS', 7)
)

# == Loging ==
ERROR_LOGS_DIR = os.path.join(LOGS_DIR, 'errors')

ERROR_LOG_FILES_CONFIG = {}

caching_errors_dir = os.path.join(ERROR_LOGS_DIR, 'caching')
os.makedirs(caching_errors_dir, exist_ok=True)
ERROR_LOG_FILES_CONFIG['caching'] = os.path.join(caching_errors_dir, 'caching_errors.log')

celery_tasks_errors_dir = os.path.join(ERROR_LOGS_DIR, 'celery_tasks')
os.makedirs(celery_tasks_errors_dir, exist_ok=True)
ERROR_LOG_FILES_CONFIG['celery_tasks'] = os.path.join(celery_tasks_errors_dir, 'celery_tasks_errors.log')

wall_config_errors_dir = os.path.join(ERROR_LOGS_DIR, 'wall_configuration')
os.makedirs(wall_config_errors_dir, exist_ok=True)
ERROR_LOG_FILES_CONFIG['wall_configuration'] = os.path.join(wall_config_errors_dir, 'wall_config_errors.log')

wall_creation_errors_dir = os.path.join(ERROR_LOGS_DIR, 'wall_creation')
os.makedirs(wall_creation_errors_dir, exist_ok=True)
ERROR_LOG_FILES_CONFIG['wall_creation'] = os.path.join(wall_creation_errors_dir, 'wall_creation_errors.log')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'the_wall_api.utils.custom_json_formatter.CustomJsonFormatter',
            'format': '%(asctime)s %(message)s %(levelname)s %(traceback)s %(request_info)s %(error_id)s',
        },
        'json_stdout': {
            '()': 'the_wall_api.utils.custom_json_formatter.CustomJsonFormatter',
            'format': '%(asctime)s %(message)s %(levelname)s %(traceback)s %(request_info)s %(error_id)s',
            'json_indent': 4,
        },
    },
    'handlers': {
        # Handler for caching errors
        'caching_errors_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': ERROR_LOG_FILES_CONFIG['caching'],
            'maxBytes': 1024 * 1024 * 5,    # 5 MB
            'backupCount': 4,
            'delay': True,
            'formatter': 'json',
        },
        # Handler for Celery tasks errors
        'celery_tasks_errors_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': ERROR_LOG_FILES_CONFIG['celery_tasks'],
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 4,
            'delay': True,
            'formatter': 'json',
        },
        # Handler for wall configuration errors
        'wall_config_errors_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': ERROR_LOG_FILES_CONFIG['wall_configuration'],
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 4,
            'delay': True,
            'formatter': 'json',
        },
        # Handler for wall creation errors
        'wall_creation_errors_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': ERROR_LOG_FILES_CONFIG['wall_creation'],
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 4,
            'delay': True,
            'formatter': 'json',
        },
        # Console logging
        'console_logger': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'json_stdout',
        },
    },
    'loggers': {
        'caching': {
            'handlers': ['caching_errors_file', 'console_logger'],
            'level': 'ERROR',
            'propagate': False,
        },
        'celery_tasks': {
            'handlers': ['celery_tasks_errors_file', 'console_logger'],
            'level': 'ERROR',
            'propagate': False,
        },
        'wall_configuration': {
            'handlers': ['wall_config_errors_file', 'console_logger'],
            'level': 'ERROR',
            'propagate': False,
        },
        'wall_creation': {
            'handlers': ['wall_creation_errors_file', 'console_logger'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# == Loging end ==

# === Filesystem configuration end ===

# Wall Configuration Settings
MAX_HEIGHT = int(os.getenv('MAX_HEIGHT', 30))                                           # Maximum height of a wall section
MAX_LENGTH = int(os.getenv('MAX_LENGTH', 2000))                                         # Maximum lenght of a wall profile
ICE_PER_FOOT = int(os.getenv('ICE_PER_FOOT', 195))                                      # Cubic yards of ice used per 1 foot height increase
ICE_COST_PER_CUBIC_YARD = int(os.getenv('ICE_COST_PER_CUBIC_YARD', 1900))               # Gold Dragon coins cost per cubic yard

# Common settings
API_VERSION = os.getenv('API_VERSION', 'v1')
