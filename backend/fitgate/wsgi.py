"""WSGI config for FitGate project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fitgate.settings.prod")

application = get_wsgi_application()
