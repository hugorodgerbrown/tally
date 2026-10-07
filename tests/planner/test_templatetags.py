"""Tests for apps.planner.templatetags.planner: time formats and equipment icons."""

import pytest

from apps.planner.templatetags.planner import duration, equipment_icon, mmss


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (None, "0 s"),
        (-3, "0 s"),
        (45, "45 s"),
        (60, "1 min"),
        (470, "7 min 50 s"),
        (3600, "1 h"),
        (3930, "1 h 6 min"),
    ],
)
def test_duration_filter(seconds: float | None, text: str) -> None:
    """A length of time reads as seconds, minutes and seconds, or hours and minutes."""
    assert duration(seconds) == text


@pytest.mark.parametrize(("seconds", "text"), [(None, "0:00"), (5, "0:05"), (125.4, "2:05")])
def test_mmss_filter(seconds: float | None, text: str) -> None:
    """Seconds read as m:ss, the way the phone shows time."""
    assert mmss(seconds) == text


def test_equipment_icon_draws_a_labelled_svg() -> None:
    """A piece of equipment is drawn as an SVG labelled with its name."""
    svg = equipment_icon("kettlebell")
    assert svg.startswith('<svg class="eq"')
    assert 'aria-label="Kettlebell"' in svg


def test_equipment_icon_is_empty_for_bodyweight() -> None:
    """No equipment draws nothing."""
    assert equipment_icon("") == ""
