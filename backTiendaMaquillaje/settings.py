"""
Django settings for backTiendaMaquillaje project.

Estructura de environments:
  - BASE_DIR / .env  →  variables de entorno locales
  - Para producción usar variables de entorno del sistema o secrets manager
"""

from pathlib import Path
from datetime import timedelta
import environ

# ─────────────────────────────────────────────
# Paths & Env
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")


# ─────────────────────────────────────────────
# Security
# ─────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="django-insecure-d-2##(cmjmf0$48qufd)yini1!+%_t#*t0u&&z(dhb0kd#(@!1")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# ─────────────────────────────────────────────
# Applications
# ─────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "cloudinary",
    "cloudinary_storage",
]

LOCAL_APPS = [
    "apps.users",
    "apps.catalog",
    "apps.inventory",
    "apps.orders",
    "apps.promotions",
    "apps.reviews",
    "apps.wishlist",
    "apps.shipping",
    "apps.payments",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ─────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",       # Sirve estáticos en prod
    "corsheaders.middleware.CorsMiddleware",            # CORS antes de CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backTiendaMaquillaje.urls"
WSGI_APPLICATION = "backTiendaMaquillaje.wsgi.application"


# ─────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        # Fallback local a SQLite mientras no tengas Postgres configurado
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
# Para PostgreSQL en producción, en .env pon:
# DATABASE_URL=postgres://user:password@localhost:5432/makeup_store


# ─────────────────────────────────────────────
# Auth & Password Validation
# ─────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"   # Modelo de usuario personalizado (app users)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ─────────────────────────────────────────────
# Internacionalización
# ─────────────────────────────────────────────
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True


# ─────────────────────────────────────────────
# Static & Media files
# ─────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Cloudinary gestiona los archivos de media (imágenes de productos)
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
MEDIA_URL = "/media/"


# ─────────────────────────────────────────────
# Cloudinary
# ─────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME", default=""),
    "API_KEY":    env("CLOUDINARY_API_KEY",    default=""),
    "API_SECRET": env("CLOUDINARY_API_SECRET", default=""),
}

# También configura el cliente de Cloudinary para transformaciones directas
import cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_STORAGE["CLOUD_NAME"],
    api_key=CLOUDINARY_STORAGE["API_KEY"],
    api_secret=CLOUDINARY_STORAGE["API_SECRET"],
    secure=True,
)


# ─────────────────────────────────────────────
# Django REST Framework
# ─────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # En desarrollo habilitamos el BrowsableAPI para testear desde el navegador
    **(
        {
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
                "rest_framework.renderers.BrowsableAPIRenderer",
            ]
        }
        if DEBUG
        else {}
    ),
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}


# ─────────────────────────────────────────────
# Simple JWT
# ─────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "apps.users.serializers.CustomTokenObtainPairSerializer",
}


# ─────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────
# En desarrollo Angular corre en localhost:4200
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
)
CORS_ALLOW_CREDENTIALS = True


# ─────────────────────────────────────────────
# Wompi (Pasarela de pagos)
# ─────────────────────────────────────────────
WOMPI_PUBLIC_KEY  = env("WOMPI_PUBLIC_KEY",  default="")
WOMPI_PRIVATE_KEY = env("WOMPI_PRIVATE_KEY", default="")
WOMPI_EVENTS_SECRET = env("WOMPI_EVENTS_SECRET", default="")  # Para validar webhooks
WOMPI_SANDBOX = env.bool("WOMPI_SANDBOX", default=True)
WOMPI_BASE_URL = (
    "https://sandbox.wompi.co/v1"
    if WOMPI_SANDBOX
    else "https://production.wompi.co/v1"
)


# ─────────────────────────────────────────────
# Cache (Redis)
# ─────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
    }
}


# ─────────────────────────────────────────────
# Celery (tareas asíncronas: emails, Wompi webhooks, etc.)
# ─────────────────────────────────────────────
CELERY_BROKER_URL         = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND     = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT     = ["json"]
CELERY_TASK_SERIALIZER    = "json"
CELERY_RESULT_SERIALIZER  = "json"
CELERY_TIMEZONE           = TIME_ZONE


# ─────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",  # Console en dev
)
EMAIL_HOST        = env("EMAIL_HOST",        default="smtp.gmail.com")
EMAIL_PORT        = env.int("EMAIL_PORT",    default=587)
EMAIL_USE_TLS     = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER   = env("EMAIL_HOST_USER",   default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL  = env("DEFAULT_FROM_EMAIL", default="noreply@tiendamaquillaje.co")


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}


# ─────────────────────────────────────────────
# Misceláneos
# ─────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Límite de subida de imágenes (10 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024