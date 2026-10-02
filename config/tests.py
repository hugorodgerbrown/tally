from django.urls import reverse


def test_healthz_needs_no_login_or_database(client):
    # No db fixture: pytest-django fails the test if the view touches the database.
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    assert response.content == b"ok"
