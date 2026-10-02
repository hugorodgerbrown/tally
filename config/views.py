from django.http import HttpRequest, HttpResponse


def healthz(request: HttpRequest) -> HttpResponse:
    """Render's health check: no sign-in and no database query."""
    return HttpResponse("ok", content_type="text/plain")
