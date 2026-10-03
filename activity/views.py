import hashlib
from functools import cache
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

# Everything the app needs to run offline. The service worker precaches
# these, plus the app shell at /activity/.
APP_ASSETS = [
    "ui/tokens.css",
    "activity/app.css",
    "activity/app.js",
    "activity/store.js",
    "activity/engine.js",
    "icons/favicon.svg",
    "icons/favicon.ico",
    "icons/apple-touch-icon.png",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "icons/icon-maskable-512.png",
]
APP_TEMPLATE = Path(__file__).parent / "templates" / "activity" / "app.html"


def assets_version() -> str:
    """Hash of the shell and asset contents; a deploy changes the cache name.

    Recomputed on every request in development so edits reach the browser.
    """
    return _hash_assets() if settings.DEBUG else _cached_hash_assets()


def _hash_assets() -> str:
    digest = hashlib.sha256(APP_TEMPLATE.read_bytes())
    for name in APP_ASSETS:
        path = finders.find(name)
        if not isinstance(path, str):
            raise ImproperlyConfigured(f"App asset {name} is missing from static files.")
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()[:12]


_cached_hash_assets = cache(_hash_assets)


@ensure_csrf_cookie
@login_required(login_url="activity:login")
def app(request: HttpRequest) -> HttpResponse:
    return render(request, "activity/app.html")


@never_cache
def service_worker(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "activity/sw.js",
        {"version": assets_version(), "assets": [static(a) for a in APP_ASSETS]},
        content_type="text/javascript",
    )


@never_cache
def retired_service_worker(request: HttpRequest) -> HttpResponse:
    """Replaces the worker that used to control the whole site from /sw.js.

    Browsers that installed the old one fetch this as its update; it clears
    the old caches and unregisters itself.
    """
    return render(request, "activity/sw-retired.js", content_type="text/javascript")


def manifest(request: HttpRequest) -> HttpResponse:
    return render(
        request, "activity/manifest.webmanifest", content_type="application/manifest+json"
    )
