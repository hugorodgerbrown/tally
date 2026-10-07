"""Security headers and the no-inline-script rule, checked on real responses."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

BASE = Path(settings.BASE_DIR)


@pytest.mark.django_db
def test_every_page_sends_a_strict_csp(client: Client) -> None:
    """Scripts only from this origin; no 'unsafe-inline' anywhere."""
    response = client.get(reverse("accounts:sign_in"))
    csp = response["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.django_db
def test_clickjacking_and_sniffing_headers(client: Client) -> None:
    """Pages can't be framed and content types aren't sniffed."""
    response = client.get(reverse("accounts:sign_in"))
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"


def template_files() -> list[Path]:
    """Every Django template in the project."""
    return sorted((BASE / "templates").rglob("*.html")) + sorted(
        (BASE / "apps").glob("*/templates/**/*.html")
    )


@pytest.mark.parametrize("path", template_files(), ids=lambda p: p.name)
def test_templates_have_no_inline_script_or_style(path: Path) -> None:
    """The CSP forbids inline code, so a template that has some is broken in production."""
    source = path.read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", source), "inline <script>"
    assert not re.search(r"\sstyle=", source), "inline style attribute"
    assert not re.search(r"\son[a-z]+=", source), "inline event handler"
