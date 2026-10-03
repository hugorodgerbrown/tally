from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def healthz(request: HttpRequest) -> HttpResponse:
    """Render's health check: no sign-in and no database query."""
    return HttpResponse("ok", content_type="text/plain")


def home(request: HttpRequest) -> HttpResponse:
    """The public front page. The installed app starts at /activity/ instead."""
    return render(request, "planner/home.html")
