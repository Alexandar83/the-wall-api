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
import sys

from dotenv import load_dotenv

ACTIVE_TESTING = True if 'test' in sys.argv else False

PROJECT_MODE = os.getenv('PROJECT_MODE', 'dev')

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

if PROJECT_MODE == 'dev':
    # No env. settings are injected in dev

    # App. DEV env. settings
    load_dotenv(dotenv_path=BASE_DIR / 'config' / 'envs' / 'dev' / 'the_wall_api_dev.env')
    # PostgreSQL DEV env. settings
    load_dotenv(dotenv_path=BASE_DIR / 'config' / 'envs' / 'dev' / 'postgres_dev.env', override=True)

SECRET_KEY = 'django-insecure-*x!p!3#xxluj9i+v6anb!laycbax0rbkefg7$wf06xj2-my63f'

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

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

# Verbosity of unit tests
# ERROR - only log errors
# FAILED - only log failed tests
# PASSED - only log passed tests
# ALL - log all tests
# NO-LOGGING - disable logging
# SUMMARY - only log tests summary
TEST_LOGGING_LEVEL = os.getenv('TEST_LOGGING_LEVEL', 'NO-LOGGING')

# Redis Configuration

REDIS_URL = os.getenv('REDIS_URL')
REDIS_DB_NUMBER = os.getenv('REDIS_DB_NUMBER', '0')

if REDIS_URL is not None:
    # Inject the password in the url for prod
    if PROJECT_MODE == 'prod_v1':
        REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
        REDIS_URL = REDIS_URL.replace('REDIS_PASSWORD', REDIS_PASSWORD)
    elif PROJECT_MODE == 'prod_v2':
        REDIS_PASSWORD = open(os.environ['REDIS_PASSWORD_FILE']).read().strip()
        REDIS_URL = REDIS_URL.replace('REDIS_PASSWORD', REDIS_PASSWORD)
    
    if not ACTIVE_TESTING:
        REDIS_URL = REDIS_URL.replace('REDIS_DB_NUMBER', REDIS_DB_NUMBER)
    else:
        # Use a separate Redis DB for testing
        REDIS_URL = REDIS_URL.replace('REDIS_DB_NUMBER', '1')

REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 2))

REDIS_SOCKET_TIMEOUT = int(os.getenv('REDIS_SOCKET_TIMEOUT', 2))

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

# Wall Configuration Settings
WALL_CONFIG_PATH = os.getenv('WALL_CONFIG_PATH', BASE_DIR / 'wall_config.json')         # Location of the wall profile configuration
MAX_HEIGHT = int(os.getenv('MAX_HEIGHT', 30))                                           # Maximum height of a wall section
MAX_LENGTH = int(os.getenv('MAX_LENGTH', 2000))                                         # Maximum lenght of a wall profile
ICE_PER_FOOT = int(os.getenv('ICE_PER_FOOT', 195))                                      # Cubic yards of ice used per 1 foot height increase
ICE_COST_PER_CUBIC_YARD = int(os.getenv('ICE_COST_PER_CUBIC_YARD', 1900))               # Gold Dragon coins cost per cubic yard

# Common settings
API_VERSION = os.getenv('API_VERSION', 'v1')
