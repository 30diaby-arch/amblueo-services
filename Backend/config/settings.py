import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

AMBLUEO_INFRA_RACINE = Path(__file__).resolve().parent.parent
AMBLUEO_UI_RACINE = AMBLUEO_INFRA_RACINE.parent / "Frontend"
DEBUG = os.getenv("AMBLUEO_INFRA_MODE", "local") == "local"
SECRET_KEY = os.getenv("AMBLUEO_SECURITE_CLE_SECRETE")
if not SECRET_KEY and DEBUG:
    SECRET_KEY = "amblueo-local-only-8uv-7kq-1xn-6sz-3yt-5mc-0wq-4pr-9gh-2bd"
if not SECRET_KEY:
    raise ImproperlyConfigured("AMBLUEO_SECURITE_CLE_SECRETE est obligatoire.")

ALLOWED_HOSTS = os.getenv("AMBLUEO_INFRA_HOTES", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "pilot",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [AMBLUEO_UI_RACINE / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("AMBLUEO_INFRA_NOM_BASE_DONNEES", "amblueo"),
    "HOST": os.getenv("AMBLUEO_INFRA_HOTE_BASE", "db"),
    "USER": os.getenv("AMBLUEO_INFRA_UTILISATEUR_BASE", "amblueo"),
    "PASSWORD": os.getenv("AMBLUEO_SECURITE_MOT_DE_PASSE_BASE", ""),
    "PORT": os.getenv("AMBLUEO_INFRA_PORT_BASE", "5432"),
}}
if DEBUG and os.getenv("AMBLUEO_INFRA_SQLITE") == "1":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": AMBLUEO_INFRA_RACINE / "local.sqlite3",
    }}
AMBLUEO_SECURITE_VALIDATEURS = (
    "UserAttributeSimilarityValidator", "MinimumLengthValidator",
    "CommonPasswordValidator", "NumericPasswordValidator",
)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation." + AMBLUEO_SECURITE_VALIDATEUR}
    for AMBLUEO_SECURITE_VALIDATEUR in AMBLUEO_SECURITE_VALIDATEURS
]
AUTH_USER_MODEL = "pilot.User"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"
LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", "Français")]
TIME_ZONE = os.getenv("AMBLUEO_INFRA_FUSEAU", "UTC")
USE_TZ = True
STATICFILES_DIRS = [AMBLUEO_UI_RACINE / "static", ("marque", AMBLUEO_UI_RACINE / "Logo")]
STATIC_URL = "/static/"
STATIC_ROOT = os.getenv("AMBLUEO_INFRA_STATIQUES", AMBLUEO_INFRA_RACINE / "staticfiles")
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }
MEDIA_ROOT = os.getenv("AMBLUEO_INFRA_JUSTIFICATIFS", AMBLUEO_INFRA_RACINE / "private")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG and os.getenv("AMBLUEO_INFRA_POSTFIX_HOTE") != "1"
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("AMBLUEO_INFRA_HOTE_SMTP", "")
EMAIL_PORT = int(os.getenv("AMBLUEO_INFRA_PORT_SMTP", "587"))
EMAIL_HOST_USER = os.getenv("AMBLUEO_INFRA_UTILISATEUR_SMTP", "")
EMAIL_HOST_PASSWORD = os.getenv("AMBLUEO_SECURITE_MOT_DE_PASSE_SMTP", "")
EMAIL_USE_TLS = os.getenv("AMBLUEO_INFRA_SMTP_STARTTLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv("AMBLUEO_INFRA_EXPEDITEUR", "robot@amblueo.example")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
SECURE_REFERRER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
