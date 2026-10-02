from django.test import override_settings
from django.urls import reverse


def test_healthz_needs_no_login_or_database(client):
    # No db fixture: pytest-django fails the test if the view touches the database.
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    assert response.content == b"ok"


def test_pages_send_a_content_security_policy(client):
    csp = client.get(reverse("login"))["Content-Security-Policy"]
    assert "script-src 'self';" in csp
    assert "frame-ancestors 'none'" in csp


@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^healthz$"])
def test_https_redirect_spares_the_health_check(client):
    # Mirrors production: Render's health check calls /healthz over plain HTTP.
    assert client.get(reverse("healthz")).status_code == 200
    response = client.get(reverse("login"))
    assert response.status_code == 301
    assert response["Location"].startswith("https://")
