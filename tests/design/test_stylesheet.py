"""Reading the stylesheet: declarations, tokens and class names."""

from apps.design import stylesheet

CSS = """
/* A comment { with braces } */
:root {
  --brand: #1d4ed8;
  --type-sm: 0.8125rem;
  --space-sm: 8px;
  --radius-card: 12px;
  --shadow-float: 0 1px 4px var(--rule);
  --font: system-ui;
}
@media (prefers-color-scheme: dark) {
  :root { --brand: #93c5fd; }
}
.button, .button--quiet:hover { color: var(--brand); background: url("data:image/svg+xml,a;b") }
@keyframes spin { to { transform: rotate(360deg); } }
"""


def test_parse_keeps_selector_context_and_value() -> None:
    """Each declaration keeps its selector, its at-rules and its whole value."""
    declarations = stylesheet.parse(CSS)
    button = [d for d in declarations if d.selector.startswith(".button")]
    assert [(d.prop, d.value) for d in button] == [
        ("color", "var(--brand)"),
        ("background", 'url("data:image/svg+xml,a;b")'),
    ]
    dark = [d for d in declarations if d.context == ("@media (prefers-color-scheme: dark)",)]
    assert dark[0].in_root
    assert any(d.selector == "to" for d in declarations)


def test_tokens_keep_the_light_scheme_and_sort_into_families() -> None:
    """A dark-scheme redefinition doesn't replace the light value."""
    found = stylesheet.tokens(stylesheet.parse(CSS))
    assert found["--brand"].value == "#1d4ed8"
    assert {name: token.family for name, token in found.items()} == {
        "--brand": "colour",
        "--type-sm": "type",
        "--space-sm": "space",
        "--radius-card": "radius",
        "--shadow-float": "shadow",
        "--font": "other",
    }


def test_class_names_skip_urls_and_at_rules() -> None:
    """A data URI or an at-rule never reads as a class."""
    assert stylesheet.class_names(CSS) == {"button", "button--quiet"}


def test_the_apps_stylesheet_reads() -> None:
    """The real stylesheet parses and has tokens."""
    assert stylesheet.tokens(stylesheet.read())
