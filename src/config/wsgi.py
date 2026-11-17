import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_wsgi_application()

try:
    from django.urls import get_resolver
    get_resolver().url_patterns
except Exception:
    pass
