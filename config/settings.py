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

# Initialize environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

PROJECT_MODE = os.getenv('PROJECT_MODE', 'dev')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

if PROJECT_MODE == 'prod':
    SECRET_KEY = os.getenv('PROD_SECRET_KEY')
    DEBUG = os.getenv('PROD_DEBUG', 'False') == 'True'
    ALLOWED_HOSTS = os.getenv('PROD_ALLOWED_HOSTS', '').split(',')
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('PROD_DB_ENGINE', 'django.db.backends.sqlite3'),
            'NAME': os.getenv('PROD_DB_NAME', BASE_DIR / 'db.sqlite3'),
        }
    }
    # Verbosity of unit tests
    # FAILED - only log failed tests
    # PASSED - only log passed tests
    # ALL - log all tests
    # NO-LOGGING - disable logging
    # SUMMARY - only log tests summary
    TEST_LOGGING_LEVEL = os.getenv('PROD_TEST_LOGGING_LEVEL', 'NO-LOGGING')
else:
    SECRET_KEY = os.getenv('DEV_SECRET_KEY')
    DEBUG = os.getenv('DEV_DEBUG', 'False') == 'True'
    ALLOWED_HOSTS = os.getenv('DEV_ALLOWED_HOSTS', '').split(',')
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DEV_DB_ENGINE', 'django.db.backends.sqlite3'),
            'NAME': os.getenv('DEV_DB_NAME', BASE_DIR / 'db.sqlite3')
        }
    }
    TEST_LOGGING_LEVEL = os.getenv('DEV_TEST_LOGGING_LEVEL', 'NO-LOGGING')

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
