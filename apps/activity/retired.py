"""Addresses from before Tally moved onto the template, kept so nothing breaks.

Until October 2026 the phone app lived at /activity/ with its own service
worker, and before that a worker at /sw.js controlled the whole site. The
planner was at /workouts/ and /exercises/, and sign-in at /login/. Old
workers fetch their script again to update, so both answer with a worker
that deletes Tally's old caches and unregisters; the pages redirect. A
phone that still had sessions waiting to upload keeps them in IndexedDB,
and the new app moves them into its outbox (static/js/activity_store.js).
"""

from django.http import HttpRequest, HttpResponse
from django.urls import path, re_path
from django.views.decorators.cache import never_cache
from django.views.generic import RedirectView

RETIRED_WORKER = """\
// Tally's old service worker, retired: the app now lives at /app/ with its own.
// Deletes the old worker's caches and unregisters, so the next visit goes
// straight to the network (and from there to /app/).
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    // Only the old names: "workouts-*", "tally-<hash>" and "tally-fonts".
    // The new worker's caches start "tally-app-" and are left alone.
    const old = /^(workouts-.*|tally-[0-9a-f]{12}|tally-fonts)$/;
    for (const key of await caches.keys()) {
      if (old.test(key)) await caches.delete(key);
    }
    await self.registration.unregister();
  })());
});
"""


@never_cache
def retired_worker(request: HttpRequest) -> HttpResponse:
    """Answer an old worker's update check with one that removes itself."""
    return HttpResponse(RETIRED_WORKER, content_type="text/javascript")


urlpatterns = [
    path("sw.js", retired_worker),
    path("activity/sw.js", retired_worker),
    path("activity/", RedirectView.as_view(pattern_name="activity:app", permanent=True)),
    path("activity/login/", RedirectView.as_view(pattern_name="accounts:sign_in")),
    path("login/", RedirectView.as_view(pattern_name="accounts:sign_in")),
    re_path(
        r"^(?P<rest>(workouts|exercises)/.*)$",
        RedirectView.as_view(url="/app/%(rest)s", permanent=True, query_string=True),
    ),
]
