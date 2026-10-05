import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable is required")
DEBUG = env_bool("DJANGO_DEBUG", False)
HTTPS = env_bool("DJANGO_HTTPS", not DEBUG)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fruitcam.urls"
WSGI_APPLICATION = "fruitcam.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("FRUITCAM_DB_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE", "init_command": "PRAGMA journal_mode=WAL;"},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.environ.get("FRUITCAM_TIME_ZONE", "America/Fortaleza")
USE_I18N = True
USE_TZ = True

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("FRUITCAM_STATIC_ROOT") or None
STATICFILES_DIRS = [FRONTEND_DIST] if FRONTEND_DIST.exists() else []
WHITENOISE_USE_FINDERS = True
WHITENOISE_MIMETYPES = {".vtt": "text/vtt; charset=utf-8", ".webmanifest": "application/manifest+json"}
WHITENOISE_IMMUTABLE_FILE_TEST = r"^/static/(assets/.+|(media|figures)/.+\.[0-9a-f]{10}\.\w+)$"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.environ.get("FRUITCAM_SESSION_SECONDS", 43200))
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = HTTPS
CSRF_FAILURE_VIEW = "core.views.csrf_failure"
SECURE_SSL_REDIRECT = HTTPS
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", 31536000 if HTTPS else 0))
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "media-src": [CSP.SELF],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "manifest-src": [CSP.SELF],
    "worker-src": [CSP.NONE],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}
if env_bool("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MODEL_PATH = Path(os.environ.get("FRUITCAM_MODEL_PATH", BASE_DIR / "models" / "belt_v2.pt"))
CAMERAS_FILE = Path(os.environ.get("FRUITCAM_CAMERAS_FILE", BASE_DIR / "config" / "cameras.json"))
RUN_DIR = Path(os.environ.get("FRUITCAM_RUN_DIR", BASE_DIR / "run"))
CAMERA_ONLINE_SECONDS = 5
UPLOAD_DIR = Path(os.environ.get("FRUITCAM_UPLOAD_DIR", BASE_DIR / "uploads"))
MAX_UPLOAD_BYTES = int(os.environ.get("FRUITCAM_MAX_UPLOAD_MB", 8)) * 1024 * 1024
MAX_IMAGE_PIXELS = int(os.environ.get("FRUITCAM_MAX_IMAGE_MEGAPIXELS", 40)) * 1000 * 1000

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.MultiPartParser"],
    "DEFAULT_THROTTLE_RATES": {"login": os.environ.get("FRUITCAM_LOGIN_RATE", "5/min")},
    "NUM_PROXIES": int(os.environ["FRUITCAM_NUM_PROXIES"]) if "FRUITCAM_NUM_PROXIES" in os.environ else None,
    "EXCEPTION_HANDLER": "core.views.api_exception_handler",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
