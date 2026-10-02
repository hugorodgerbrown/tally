import hashlib
from functools import cache
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

# Everything the app needs to run offline. The service worker precaches
# these, plus the app shell at "/".
APP_ASSETS = [
    "ui/tokens.css",
    "activity/app.css",
    "activity/app.js",
    "activity/store.js",
    "activity/engine.js",
    "activity/icon.svg",
    "activity/icon-192.png",
    "activity/icon-512.png",
]
APP_TEMPLATE = Path(__file__).parent / "templates" / "activity" / "app.html"


def assets_version():
    """Hash of the shell and asset contents; a deploy changes the cache name.

    Recomputed on every request in development so edits reach the browser.
    """
    return _hash_assets() if settings.DEBUG else _cached_hash_assets()


def _hash_assets():
    digest = hashlib.sha256(APP_TEMPLATE.read_bytes())
    for name in APP_ASSETS:
        digest.update(Path(finders.find(name)).read_bytes())
    return digest.hexdigest()[:12]


_cached_hash_assets = cache(_hash_assets)


@ensure_csrf_cookie
@login_required
def app(request):
    return render(request, "activity/app.html")


@never_cache
def service_worker(request):
    response = render(
        request,
        "activity/sw.js",
        {"version": assets_version(), "assets": [static(a) for a in APP_ASSETS]},
        content_type="text/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


def manifest(request):
    return render(
        request, "activity/manifest.webmanifest", content_type="application/manifest+json"
    )
