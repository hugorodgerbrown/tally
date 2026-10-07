"""Views for notes.

``note_create`` takes a plain form post (no JavaScript) or the outbox's
JSON. Either way the write is idempotent when the request carries an
``Idempotency-Key``, which the outbox always sends.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.core.decorators import login_required_json, require_htmx, signed_in_user
from apps.notes.forms import NoteForm
from apps.notes.models import Note

PAGE_SIZE = 50


def _notes_for(request: HttpRequest) -> list[Note]:
    """Return the signed-in user's latest notes."""
    return list(Note.objects.for_user(signed_in_user(request))[:PAGE_SIZE])


@require_GET
@login_required
def note_list(request: HttpRequest) -> HttpResponse:
    """The notes page: the form and the user's notes. The manifest's start_url."""
    return render(
        request, "notes/note_list.html", {"notes": _notes_for(request), "form": NoteForm()}
    )


@require_GET
@login_required_json
@require_htmx
def note_items(request: HttpRequest) -> HttpResponse:
    """The list of notes alone, refreshed by htmx after the outbox sends."""
    return render(request, "notes/_note_items.html", {"notes": _notes_for(request)})


@require_POST
@login_required_json
def note_create(request: HttpRequest) -> HttpResponse:
    """Save a note from a form post or from the outbox's JSON."""
    is_json = request.content_type == "application/json"
    if is_json:
        try:
            data = json.loads(request.body)
        except ValueError:
            return JsonResponse({"errors": {"__all__": ["Not JSON."]}}, status=400)
        if not isinstance(data, dict):
            return JsonResponse({"errors": {"__all__": ["Expected an object."]}}, status=400)
        form = NoteForm(data)
    else:
        form = NoteForm(request.POST)

    if not form.is_valid():
        if is_json:
            return JsonResponse({"errors": form.errors}, status=400)
        return render(
            request,
            "notes/note_list.html",
            {"notes": _notes_for(request), "form": form},
            status=400,
        )

    note = form.save(commit=False)
    note.owner = signed_in_user(request)
    note.save()
    if is_json:
        return JsonResponse(
            {"uuid": str(note.uuid), "text": note.text, "written_at": note.written_at.isoformat()},
            status=201,
        )
    return redirect("notes:list")
