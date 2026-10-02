from django.http import HttpResponse


def healthz(request):
    """Render's health check: no sign-in and no database query."""
    return HttpResponse("ok", content_type="text/plain")
