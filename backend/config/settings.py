from datetime import timedelta
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from local .env file
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE_DIR / '.env')
except ImportError:
    pass

from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key')
DEBUG = os.environ.get('DEBUG', '1') == '1'

if not DEBUG and (not SECRET_KEY or SECRET_KEY == 'django-insecure-dev-key'):
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_yasg',
    
    # Local apps
    'apps.accounts.apps.AccountsConfig',
    'apps.catalog.apps.CatalogConfig',
    'apps.marketplace.apps.MarketplaceConfig',
    'apps.billing.apps.BillingConfig',
    'apps.payments.apps.PaymentsConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.portfolio.apps.PortfolioConfig',
    'apps.favorites.apps.FavoritesConfig',
    'apps.comments.apps.CommentsConfig',
    'apps.reports.apps.ReportsConfig',
    'apps.messaging.apps.MessagingConfig',  # NEW
    'apps.audit.apps.AuditConfig',
    'apps.ai.apps.AiConfig',
    'apps.core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES['default'] = dj_database_url.config(conn_max_age=600)

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('DRF_THROTTLE_ANON', '100/day'),
        'user': os.environ.get('DRF_THROTTLE_USER', '1000/day'),
        'provider_geocoding': os.environ.get('DRF_THROTTLE_PROVIDER_GEOCODING', '30/minute'),
        'media_upload': os.environ.get('MEDIA_UPLOAD_THROTTLE_RATE', '10/min'),
    }
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_COOKIE': 'refresh_token',  # Custom setting for views
    'AUTH_COOKIE_SECURE': not DEBUG,
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_PATH': '/',
    'AUTH_COOKIE_SAMESITE': 'Lax',
}

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS_ALLOW_CREDENTIALS = True

# CSRF
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')

# Celery
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
Celery_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Swagger
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    }
}

# AI Integration Settings
# Provider type: "generic_openai_compatible" works with OpenAI, OpenRouter, DeepSeek, Ollama, vLLM, etc.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "generic_openai_compatible")
AI_API_KEY = os.environ.get("AI_API_KEY", "") or ""
AI_API_URL = os.environ.get("AI_API_URL", "") or ""
AI_API_MODEL = os.environ.get("AI_API_MODEL", "") or ""


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


AI_TIMEOUT_SECONDS = _safe_int(os.environ.get("AI_TIMEOUT_SECONDS"), 15)
AI_MAX_INPUT_CHARS = _safe_int(os.environ.get("AI_MAX_INPUT_CHARS"), 2000)
AI_MAX_OUTPUT_TOKENS = _safe_int(os.environ.get("AI_MAX_OUTPUT_TOKENS"), 500)
AI_TEMPERATURE = _safe_float(os.environ.get("AI_TEMPERATURE"), 0.7)


def _safe_bool(value, default):
    if value is None:
        return default
    val_str = str(value).lower()
    if val_str in ('true', '1', 'yes', 'on'):
        return True
    if val_str in ('false', '0', 'no', 'off'):
        return False
    return default


PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock")
PAYMENT_MOCK_ENABLED = _safe_bool(os.environ.get("PAYMENT_MOCK_ENABLED"), DEBUG)
BILLING_DEMO_ENABLED = _safe_bool(os.environ.get("BILLING_DEMO_ENABLED"), False)
PAYMENT_API_URL = os.environ.get("PAYMENT_API_URL", "") or ""
PAYMENT_SECRET_KEY = os.environ.get("PAYMENT_SECRET_KEY", "") or ""
PAYMENT_PUBLIC_KEY = os.environ.get("PAYMENT_PUBLIC_KEY", "") or ""
PAYMENT_WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "") or ""
PAYMENT_RETURN_URL = os.environ.get("PAYMENT_RETURN_URL", "http://localhost:3000/dashboard/orders/{order_id}/")
PAYMENT_CANCEL_URL = os.environ.get("PAYMENT_CANCEL_URL", "http://localhost:3000/dashboard/orders/{order_id}/")
PAYMENT_TIMEOUT_SECONDS = _safe_int(os.environ.get("PAYMENT_TIMEOUT_SECONDS"), 15)

# 2GIS Geocoding Settings
DGIS_API_KEY = os.environ.get("DGIS_API_KEY", "")
DGIS_API_URL = os.environ.get("DGIS_API_URL", "https://catalog.api.2gis.com/3.0/items/geocode")
DGIS_GEOCODING_ENABLED = _safe_bool(os.environ.get("DGIS_GEOCODING_ENABLED"), False) and bool(DGIS_API_KEY)
DGIS_TIMEOUT_SECONDS = _safe_int(os.environ.get("DGIS_TIMEOUT_SECONDS"), 10)
DGIS_GEOCODING_CACHE_SECONDS = _safe_int(os.environ.get("DGIS_GEOCODING_CACHE_SECONDS"), 86400)
DGIS_GEOCODING_MAX_QUERY_LENGTH = _safe_int(os.environ.get("DGIS_GEOCODING_MAX_QUERY_LENGTH"), 200)
DGIS_GEOCODING_RESULT_LIMIT = _safe_int(os.environ.get("DGIS_GEOCODING_RESULT_LIMIT"), 5)

# Media Storage Configuration
from apps.core.storage import build_media_storages_config

MEDIA_STORAGE_PROVIDER = os.environ.get("MEDIA_STORAGE_PROVIDER", "local").strip().lower()
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "")
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
AWS_QUERYSTRING_AUTH = _safe_bool(os.environ.get("AWS_QUERYSTRING_AUTH"), True)
AWS_S3_ADDRESSING_STYLE = os.environ.get("AWS_S3_ADDRESSING_STYLE", "")
AWS_S3_SIGNATURE_VERSION = os.environ.get("AWS_S3_SIGNATURE_VERSION", "")

# Image Validation & Limit Configurations
MEDIA_MAX_IMAGE_SIZE_MB = _safe_float(os.environ.get("MEDIA_MAX_IMAGE_SIZE_MB"), 5.0)
MEDIA_MAX_SOURCE_IMAGE_PIXELS = _safe_int(os.environ.get("MEDIA_MAX_SOURCE_IMAGE_PIXELS"), 50000000)
MEDIA_ALLOWED_IMAGE_TYPES = os.environ.get("MEDIA_ALLOWED_IMAGE_TYPES", "image/jpeg,image/png,image/webp")
MEDIA_MAX_IMAGE_WIDTH = _safe_int(os.environ.get("MEDIA_MAX_IMAGE_WIDTH"), 4096)
MEDIA_MAX_IMAGE_HEIGHT = _safe_int(os.environ.get("MEDIA_MAX_IMAGE_HEIGHT"), 4096)
MEDIA_IMAGE_JPEG_QUALITY = _safe_int(os.environ.get("MEDIA_IMAGE_JPEG_QUALITY"), 85)
MEDIA_IMAGE_WEBP_QUALITY = _safe_int(os.environ.get("MEDIA_IMAGE_WEBP_QUALITY"), 85)
MEDIA_UPLOAD_THROTTLE_RATE = os.environ.get("MEDIA_UPLOAD_THROTTLE_RATE", "10/min")

STORAGES = build_media_storages_config(
    provider=MEDIA_STORAGE_PROVIDER,
    media_root=MEDIA_ROOT,
    media_url=MEDIA_URL,
    access_key=AWS_ACCESS_KEY_ID,
    secret_key=AWS_SECRET_ACCESS_KEY,
    bucket_name=AWS_STORAGE_BUCKET_NAME,
    endpoint_url=AWS_S3_ENDPOINT_URL,
    region_name=AWS_S3_REGION_NAME,
    custom_domain=AWS_S3_CUSTOM_DOMAIN,
    querystring_auth=AWS_QUERYSTRING_AUTH,
    addressing_style=AWS_S3_ADDRESSING_STYLE,
    signature_version=AWS_S3_SIGNATURE_VERSION,
)


# Billing & Payment Settings
BILLING_PAYMENT_PROVIDER = os.environ.get("BILLING_PAYMENT_PROVIDER", "mock")
BILLING_RETURN_URL = os.environ.get("BILLING_RETURN_URL", "http://localhost:3000/{locale}/provider/billing")
BILLING_CANCEL_URL = os.environ.get("BILLING_CANCEL_URL", "http://localhost:3000/{locale}/provider/billing")
BILLING_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS = _safe_int(os.environ.get("BILLING_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS"), 60)
BILLING_PAYMENT_TIMEOUT_SECONDS = _safe_int(os.environ.get("BILLING_PAYMENT_TIMEOUT_SECONDS"), 15)
BILLING_PENDING_CHECKOUT_MINUTES = _safe_int(os.environ.get("BILLING_PENDING_CHECKOUT_MINUTES"), 30)

# Webhook security: HMAC-SHA256 shared secret (never commit a real value)
BILLING_PAYMENT_WEBHOOK_SECRET = os.environ.get("BILLING_PAYMENT_WEBHOOK_SECRET", "")

# Stale webhook event reclaim timeout in seconds (default: 120)
BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS = _safe_int(
    os.environ.get("BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS"), 120
)

# PayPal Configuration & Sandbox Conversion Settings
from decimal import Decimal

PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")
PAYPAL_API_BASE_URL = os.environ.get("PAYPAL_API_BASE_URL", "https://api-m.sandbox.paypal.com")

PAYPAL_SANDBOX_CONVERSION_ENABLED = _safe_bool(os.environ.get("PAYPAL_SANDBOX_CONVERSION_ENABLED"), True)
PAYPAL_SANDBOX_KZT_PER_USD = Decimal(os.environ.get("PAYPAL_SANDBOX_KZT_PER_USD", "450.00"))
PAYPAL_SANDBOX_CURRENCY = os.environ.get("PAYPAL_SANDBOX_CURRENCY", "USD")

PAYPAL_BILLING_CLIENT_ID = os.environ.get("PAYPAL_BILLING_CLIENT_ID", "")
PAYPAL_BILLING_CLIENT_SECRET = os.environ.get("PAYPAL_BILLING_CLIENT_SECRET", "")
PAYPAL_BILLING_WEBHOOK_ID = os.environ.get("PAYPAL_BILLING_WEBHOOK_ID", "")

PAYPAL_ORDERS_CLIENT_ID = os.environ.get("PAYPAL_ORDERS_CLIENT_ID", "")
PAYPAL_ORDERS_CLIENT_SECRET = os.environ.get("PAYPAL_ORDERS_CLIENT_SECRET", "")
PAYPAL_ORDERS_WEBHOOK_ID = os.environ.get("PAYPAL_ORDERS_WEBHOOK_ID", "")
PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS = _safe_int(
    os.environ.get("PAYPAL_CHECKOUT_INITIALIZATION_TIMEOUT_SECONDS"), 300
)

BILLING_PAYMENT_MODE = os.environ.get("BILLING_PAYMENT_MODE", "sandbox")
PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "sandbox")

BACKEND_API_BASE_URL = os.environ.get("BACKEND_API_BASE_URL", "http://localhost:8000")
PUBLIC_BACKEND_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8000")




