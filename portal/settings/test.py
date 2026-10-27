from .common import *

DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.path.join(BASE_DIR, "test.sqlite3"),}}

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = os.path.join(BASE_DIR, "logs")

CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True


AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]
