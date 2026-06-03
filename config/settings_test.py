"""Test settings: inherit everything, force a fast in-memory sqlite DB.

Using a dedicated settings module (rather than an env var) makes the test
database deterministic regardless of plugin/conftest import order.
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# A long key so JWT/HMAC doesn't warn about key length in tests.
SECRET_KEY = "test-secret-key-long-enough-for-hmac-sha256-padding-1234567890"

# Faster password hashing in tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Disable throttling so the suite isn't rate-limited.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": ()}  # noqa: F405

# WhiteNoise isn't needed in tests (no collected static dir).
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405
