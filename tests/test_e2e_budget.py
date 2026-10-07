"""Keep the browser suite small: few journeys, each short, each named.

A browser test is the slowest and flakiest kind. Anything the Django test
client can see belongs in pytest; anything jsdom can see belongs in
tests/js. See docs/testing.md.
"""

import ast
from pathlib import Path

E2E = Path(__file__).parent / "e2e"
MAX_TESTS = 12
MAX_LINES = 40


def e2e_tests() -> list[tuple[Path, ast.FunctionDef]]:
    """Every test function in tests/e2e."""
    found = []
    for path in sorted(E2E.glob("test_*.py")):
        tree = ast.parse(path.read_text())
        found += [
            (path, node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        ]
    return found


def test_suite_stays_small() -> None:
    """Raising MAX_TESTS is a deliberate change, with a reason in the PR."""
    assert len(e2e_tests()) <= MAX_TESTS


def test_each_journey_is_short() -> None:
    """A journey longer than MAX_LINES is testing details a lower layer should hold."""
    for path, node in e2e_tests():
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        assert length <= MAX_LINES, f"{path.name}::{node.name} is {length} lines"


def test_each_module_names_its_scenario() -> None:
    """Every journey maps to a scenario in docs/testing.md."""
    for path in sorted(E2E.glob("test_*.py")):
        assert "Scenario:" in (ast.get_docstring(ast.parse(path.read_text())) or ""), path.name
