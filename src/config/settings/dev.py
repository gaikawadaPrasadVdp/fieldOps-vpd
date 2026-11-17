from .base import *  # noqa: F401,F403

DEBUG = True
INTERNAL_IPS = ["127.0.0.1"]
STORAGES = {  # no manifest build step needed in development
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Ensure templates reload on every request in development without memory caching
TEMPLATES[0]["APP_DIRS"] = False
TEMPLATES[0]["OPTIONS"]["loaders"] = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

