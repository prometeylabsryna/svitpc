from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = ["testserver"]

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "svitpc_test",
        "USER": "svitpc",
        "PASSWORD": "svitpc",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

AXES_ENABLED = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# pgvector extension may not be available in CI/local test DB;
# skip the embedding migration to keep tests runnable without it.
# The field is nullable, so existing tests are unaffected.
MIGRATION_MODULES = {
    "catalog": "apps.catalog.migrations_no_vector",
}
