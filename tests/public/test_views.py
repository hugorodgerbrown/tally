"""Tests for apps.public.views: the homepage, terms, privacy and help."""

import re

import pytest
from django.test import Client
from django.urls import reverse

from apps.public import views
from apps.pwa import conf

pytestmark = pytest.mark.django_db


PAGES = ["public:home", "public:terms", "public:privacy", "public:help"]


@pytest.mark.parametrize("name", PAGES)
def test_public_pages_need_no_sign_in(client: Client, name: str) -> None:
    """Anyone can read them, and they link to each other."""
    response = client.get(reverse(name))
    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("public:terms") in content
    assert reverse("public:privacy") in content
    assert reverse("public:help") in content


@pytest.mark.parametrize("name", PAGES)
def test_public_pages_are_outside_the_app(client: Client, name: str) -> None:
    """No manifest, worker or outbox: the installed app is /app/ alone."""
    content = client.get(reverse(name)).content.decode()
    assert "manifest" not in content
    assert "pwa.js" not in content


MCP_URL = "https://example.test/mcp"


@pytest.fixture
def with_mcp(monkeypatch: pytest.MonkeyPatch) -> str:
    """The front page and help as an app that serves /mcp sees them."""
    monkeypatch.setattr(views, "mcp_url", lambda: MCP_URL)
    return MCP_URL


@pytest.fixture
def without_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """The front page and help as an app made without MCP sees them."""
    monkeypatch.setattr(views, "mcp_url", lambda: "")


def primary_actions(content: str) -> list[tuple[str, str]]:
    """The front page's primary actions, as (href, label): the block buttons."""
    pattern = r'<a class="button button--block" href="([^"]*)">([^<]*)</a>'
    return [(match[1], match[2]) for match in re.finditer(pattern, content)]


def test_home_has_one_promise(client: Client) -> None:
    """One H1, and it is the promise, not the app's name (the header says that)."""
    content = client.get(reverse("public:home")).content.decode()
    assert content.count("<h1") == 1
    h1 = re.search(r"<h1>(.*?)</h1>", content)
    assert h1
    assert h1.group(1) != conf.APP_NAME


def test_home_offers_one_way_in(client: Client) -> None:
    """Signed out, both primary actions go to sign in, onwards to the first job."""
    content = client.get(reverse("public:home")).content.decode()
    first_job = f"{reverse('accounts:sign_in')}?next={reverse('planner:workout_new')}"
    actions = primary_actions(content)
    assert len(actions) == 2
    assert {href for href, _label in actions} == {first_job}
    assert len({label for _href, label in actions}) == 1
    assert "Create an account" not in content


def test_home_opens_the_app_when_signed_in(signed_in: Client) -> None:
    """Signed in, the header and both primary actions open the app instead."""
    content = signed_in.get(reverse("public:home")).content.decode()
    actions = primary_actions(content)
    assert actions == [(reverse("activity:app"), "Open the app")] * 2
    header = content[content.index("<header") : content.index("</header>")]
    assert "Open the app" in header
    assert "Sign in" not in content


def test_home_shows_the_product_with_demo_data(client: Client) -> None:
    """The phone's own finish screen, drawn by activity.css with a demo workout, not a picture."""
    content = client.get(reverse("public:home")).content.decode()
    showcase = content.split('class="showcase"')[1].split("</figure>")[0]
    assert "css/activity.css" in content
    assert 'id="app" class="embedded"' in showcase
    assert 'class="scr s-done"' in showcase
    assert 'class="tbar"' in showcase
    assert 'class="mus"' in showcase
    assert views.DEMO_NAME in showcase
    assert "7 min 50 s" in showcase
    assert "<img" not in showcase


def test_demo_report_matches_the_phone() -> None:
    """Time by type is split evenly, time by muscle counts in full, as engine.js does it."""
    report = views.demo_report()
    assert report["worked"] == 470  # Split squat is worked once per side
    assert sum(t["seconds"] for t in report["types"]) == report["worked"]
    assert [t["name"] for t in report["types"]] == ["Strength", "Fitness", "Aerobic"]
    assert report["types"][0]["seconds"] == 385
    assert report["types"][0]["colour"].startswith("#")
    assert report["muscles"][0] == {"name": "Glutes", "seconds": 320, "percent": 100}
    assert len(report["muscles"]) == views.DEMO_MUSCLES


def test_demo_report_saves_nothing() -> None:
    """Drawing the front page writes no rows."""
    from apps.activity.models import ActivitySession
    from apps.library.models import Exercise, Workout

    views.demo_report()
    assert not Workout.objects.exists()
    assert not Exercise.objects.exists()
    assert not ActivitySession.objects.exists()


def test_home_shows_the_connector(client: Client, with_mcp: str) -> None:
    """With MCP: a sample chat, things to ask, the address to copy and the steps' link."""
    content = client.get(reverse("public:home")).content.decode()
    assert 'class="chat"' in content
    assert 'class="asks"' in content
    assert f'data-copy="{with_mcp}"' in content
    assert f'href="{reverse("public:help")}#use-with-ai"' in content
    assert "js/copy.js" in content


def test_home_leaves_the_connector_out_without_mcp(client: Client, without_mcp: None) -> None:
    """An app made without MCP has no AI-chat section."""
    content = client.get(reverse("public:home")).content.decode()
    assert 'class="chat"' not in content
    assert "data-copy" not in content


def test_help_gives_the_steps_for_claude_and_chatgpt(client: Client, with_mcp: str) -> None:
    """The steps every Titan app shares, around the address to copy."""
    content = client.get(reverse("public:help")).content.decode()
    assert 'id="use-with-ai"' in content
    assert "<h3>Claude</h3>" in content
    assert "<h3>ChatGPT</h3>" in content
    assert f'data-copy="{with_mcp}"' in content


def test_help_leaves_the_steps_out_without_mcp(client: Client, without_mcp: None) -> None:
    """No connector, no steps."""
    content = client.get(reverse("public:help")).content.decode()
    assert 'id="use-with-ai"' not in content
    assert "data-copy" not in content
