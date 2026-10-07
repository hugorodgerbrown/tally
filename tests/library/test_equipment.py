"""Tests for apps.library.equipment: the kit icons."""

from apps.library.equipment import equipment_json, icon_svg


def test_icon_for_bodyweight_is_empty() -> None:
    """No kit, or kit with no icon, draws nothing."""
    assert icon_svg("") == ""
    assert icon_svg("barbell") == ""


def test_icon_is_labelled() -> None:
    """Each icon names itself for screen readers."""
    svg = icon_svg("kettlebell")
    assert svg.startswith('<svg class="eq" viewBox="0 0 24 24" role="img" aria-label="Kettlebell">')
    assert "<title>Kettlebell</title>" in svg


def test_equipment_json_lists_every_choice() -> None:
    """The phone gets every icon, so it can draw them offline."""
    assert {e["slug"] for e in equipment_json()} == {"kettlebell", "dumbbell"}
