"""Django settings for the workouts project.

Configuration that differs between environments comes from environment
variables; the defaults suit local development.
"""

import os
from pathlib import Path

import dj_database_url
from django.utils.csp import CSP
from mcp_auth.conf import oauth2_settings

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-local-development-only" if DEBUG else ""
)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Render sets this to the service's onrender.com name.
if RENDER_EXTERNAL_HOSTNAME := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Render terminates TLS and forwards plain HTTP with X-Forwarded-Proto set.
# Its health check calls /healthz over plain HTTP, so that path is not
# redirected.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# HSTS preload needs a registrable domain of our own; an onrender.com name
# can't be preloaded.
SILENCED_SYSTEM_CHECKS = [
    "security.W021",
    # OAuth allows http redirect URIs because Claude Code and other local MCP
    # clients sign in through a loopback port (RFC 8252). Registration only
    # accepts http for loopback; see mcp_auth's redirect allowlist.
    "oauth2_provider.W008",
]

# Content Security Policy. Scripts only from this site (no inline scripts).
# Styles allow inline because templates set colours and widths per row; fonts
# come from Google Fonts, which the service worker also fetches and caches.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://fonts.googleapis.com"],
    "font-src": [CSP.SELF, "https://fonts.gstatic.com"],
    "img-src": [CSP.SELF, "data:"],
    "connect-src": [CSP.SELF, "https://fonts.googleapis.com", "https://fonts.gstatic.com"],
    "worker-src": [CSP.SELF],
    "manifest-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "library",
    "activity",
    "planner",
    # Before mcp_auth so its consent and connected-apps templates win.
    "mcp_server",
    "mcp_auth",
    "oauth2_provider",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASE_URL (Postgres in production) wins; otherwise a local SQLite file.
if DATABASE_URL := os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# One account signs in to both the desktop planner and the PWA. The session
# lasts a year so the phone keeps syncing without asking for the password.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "planner:workouts"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# OAuth 2.1 for the MCP server, so Claude can connect to /mcp as a connector.
# The shared Titan preset (mcp_auth): PKCE, rotating refresh tokens,
# DCR and CIMD, held to Claude's callbacks and loopback. Only the superuser
# may connect. The scope keeps its original name so live connections survive.
OAUTH2_PROVIDER = oauth2_settings(
    resource_name="Tally",
    scope="tally",
    scope_description="Read and change your exercises, workouts and sessions",
)
MCP_AUTH = {
    "SCOPE": "tally",
    "CAN_CONNECT": "mcp_auth.policy.superuser_only",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
