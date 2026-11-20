"""Isolated settings for running tests without connecting to Supabase."""

from .settings import *  # noqa: F403

SECRET_KEY = 'django-insecure-dashboard-test-only'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}
