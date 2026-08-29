"""
Test settings optimized for fast test suite execution.
"""

from .base import *

DEBUG = False

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Fast, self-contained in-memory database for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
