"""Tests for apps.notes.views."""

import json
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.notes.models import Note
from tests.factories import NoteFactory, UserFactory

CREATE = reverse("notes:create")


def post_json(client: Client, data: Any) -> Any:
    """POST ``data`` as JSON to the create endpoint."""
    return client.post(CREATE, json.dumps(data), content_type="application/json")


def test_list_needs_sign_in(client: Client) -> None:
    """Signed-out visitors are sent to sign in."""
    assert client.get(reverse("notes:list")).status_code == 302


def test_list_shows_only_my_notes(signed_in: Client, user: Any) -> None:
    """A user sees their own notes and nobody else's."""
    NoteFactory.create(owner=user, text="mine")
    NoteFactory.create(text="theirs")
    response = signed_in.get(reverse("notes:list"))
    assert b"mine" in response.content
    assert b"theirs" not in response.content


def test_list_query_count_is_flat(
    signed_in: Client, user: Any, django_assert_max_num_queries: Any
) -> None:
    """Fifty notes cost no more queries than one (no N+1)."""
    NoteFactory.create_batch(50, owner=user)
    with django_assert_max_num_queries(4):
        signed_in.get(reverse("notes:list"))


def test_create_from_json(signed_in: Client, user: Any) -> None:
    """The outbox's JSON creates a note and answers 201 with it."""
    written = (timezone.now() - timedelta(hours=3)).replace(microsecond=0)
    response = post_json(signed_in, {"text": "offline", "written_at": written.isoformat()})
    assert response.status_code == 201
    note = Note.objects.get()
    assert note.owner == user
    assert note.written_at == written
    assert response.json()["uuid"] == str(note.uuid)


def test_create_from_form_post(signed_in: Client) -> None:
    """Without JavaScript the form posts and redirects back to the list."""
    response = signed_in.post(CREATE, {"text": "plain"})
    assert response.status_code == 302
    assert Note.objects.get().text == "plain"


def test_create_form_errors_rerender_the_page(signed_in: Client) -> None:
    """An invalid form post shows the page again with a 400."""
    response = signed_in.post(CREATE, {"text": ""})
    assert response.status_code == 400
    assert b"This field is required" in response.content


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"text": ""}, 400),
        ({"text": "x", "written_at": "2999-01-01T00:00:00Z"}, 400),
        ({"text": "x", "written_at": "2000-01-01T00:00:00Z"}, 400),
        (["not", "an", "object"], 400),
    ],
)
def test_create_rejects_bad_json(signed_in: Client, body: Any, status: int) -> None:
    """Invalid input is a 400, which the outbox treats as a permanent failure."""
    assert post_json(signed_in, body).status_code == status
    assert not Note.objects.exists()


def test_create_rejects_malformed_json(signed_in: Client) -> None:
    """A body that isn't JSON is a 400."""
    response = signed_in.post(CREATE, "{nope", content_type="application/json")
    assert response.status_code == 400


def test_create_signed_out_is_401_not_a_redirect(client: Client, db: None) -> None:
    """The outbox must see 401 (keep and wait), never a redirect to the sign-in page."""
    assert post_json(client, {"text": "x"}).status_code == 401


def test_items_partial_needs_htmx(signed_in: Client) -> None:
    """The fragment refuses plain requests."""
    url = reverse("notes:items")
    assert signed_in.get(url).status_code == 400
    assert signed_in.get(url, headers={"HX-Request": "true"}).status_code == 200


def test_notes_are_per_user_in_the_partial(signed_in: Client) -> None:
    """The fragment shows only the signed-in user's notes."""
    NoteFactory.create(owner=UserFactory.create(), text="someone else")
    response = signed_in.get(reverse("notes:items"), headers={"HX-Request": "true"})
    assert b"someone else" not in response.content
    assert b"No notes yet" in response.content
