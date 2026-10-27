"""
WSGI config for portal project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = os.environ.get("DJANGO_SETTINGS_MODULE") or os.environ["django_settings_module"]

application = get_wsgi_application()
