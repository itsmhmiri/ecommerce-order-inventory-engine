import os

# Default to development settings if not specified
env_settings = os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.development")
