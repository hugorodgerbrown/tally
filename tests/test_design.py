"""The design rules in DESIGN.md, checked against the stylesheet and its users.

Each test is one rule. A failure names the selector and the value, so the
fix is to use (or add) a token, or show the component on the design page,
not to loosen the test.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.design import stylesheet
from apps.design.conf import ADDED_BY_FRAMEWORKS, NOT_ON_PAGE

BASE = Path(settings.BASE_DIR)

# The limits in DESIGN.md.
MAX_COLOURS = 20
MAX_TYPE_SIZES = 8
MAX_RADII = 5
MAX_SHADOWS = 4

# The shared spacing scale: every --space-* token is one of these.
SPACE_SCALE = {
    "--space-2xs": "2px",
    "--space-xs": "4px",
    "--space-sm": "8px",
    "--space-md": "12px",
    "--space-lg": "16px",
    "--space-xl": "20px",
    "--space-2xl": "24px",
    "--space-3xl": "32px",
    "--space-4xl": "48px",
}

SPACING_PROPERTIES = re.compile(r"^(?:margin|padding)(?:-[a-z-]+)?$|^(?:row-|column-)?gap$")
LENGTH = re.compile(r"(?<![\w-])-?\d*\.?\d+(?:px|rem|em|%|vh|vw|dvh|ch)\b")
TOKEN_REF = re.compile(r"var\(--[\w-]+\)")
MASK_PROPERTIES = {"mask", "mask-image", "-webkit-mask", "-webkit-mask-image"}

DECLARATIONS = stylesheet.read()
RULES = [d for d in DECLARATIONS if not d.in_root]
TOKENS = stylesheet.tokens(DECLARATIONS)
CSS = stylesheet.stylesheet_path().read_text()


def where(declaration: stylesheet.Declaration) -> str:
    """A declaration as a failure message names it."""
    return f"{declaration.selector} {{ {declaration.prop}: {declaration.value} }}"


def literal_lengths(value: str) -> list[str]:
    """The lengths in a value that aren't tokens (``0`` is not a length here)."""
    value = TOKEN_REF.sub("", value)
    value = re.sub(r"env\([^)]*\)", "", value)
    return LENGTH.findall(value)


def without_urls(value: str) -> str:
    """A value with its ``url(...)`` parts taken out."""
    return re.sub(r"url\((?:[^()]|\([^()]*\))*\)", "", value)


def family(name: str) -> list[stylesheet.Token]:
    """The tokens in one family."""
    return [token for token in TOKENS.values() if token.family == name]


def source_files() -> list[Path]:
    """Every file that can put a class on a screen: templates, scripts, Python.

    The design page (apps/design) is left out: it shows every component, so
    counting it would keep a component alive after its last real use.
    """
    files = sorted((BASE / "templates").rglob("*.html"))
    files += sorted((BASE / "apps").glob("*/templates/**/*.html"))
    files += sorted((BASE / "static" / "js").rglob("*.js"))
    files += sorted((BASE / "static" / "vendor").rglob("*.js"))
    files += sorted(p for p in (BASE / "apps").rglob("*.py") if "migrations" not in p.parts)
    design = BASE / "apps" / "design"
    return [path for path in files if design not in path.parents and path.name != "design.js"]


SOURCES = "\n".join(path.read_text() for path in source_files())


def is_used(name: str) -> bool:
    """Whether a class appears in the sources, whole or built from a prefix.

    ``chip--{{ kind }}`` in a template, or ``"chip--" + kind`` in a script,
    counts as using every ``chip--*`` class.
    """
    if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", SOURCES):
        return True
    for i, char in enumerate(name):
        if char in "-_" and i > 0:
            prefix = re.escape(name[: i + 1])
            if re.search(rf"(?<![\w-]){prefix}(?:\{{\{{|\{{%|\$\{{|[\"']\s*\+)", SOURCES):
                return True
    return False


# --- Colour --------------------------------------------------------------


def test_colours_are_only_written_as_tokens() -> None:
    """A colour literal outside :root is a colour the design system doesn't know."""
    found = [where(d) for d in RULES if stylesheet.COLOUR_LITERAL.search(without_urls(d.value))]
    assert not found, "use a colour token: " + "; ".join(found)


def test_svg_images_are_masks_painted_with_tokens() -> None:
    """An SVG in a data URI carries its own colours, so it may only be a mask."""
    found = [
        where(d) for d in RULES if "data:image/svg" in d.value and d.prop not in MASK_PROPERTIES
    ]
    assert not found, "use mask-image with a token background: " + "; ".join(found)


def script_and_template_files() -> list[Path]:
    """Scripts and templates that could carry a colour (emails aside)."""
    files = sorted((BASE / "static" / "js").rglob("*.js"))
    files += sorted((BASE / "templates").rglob("*.html"))
    files += sorted((BASE / "apps").glob("*/templates/**/*.html"))
    return [path for path in files if "email" not in path.parts]


@pytest.mark.parametrize("path", script_and_template_files(), ids=lambda p: p.name)
def test_scripts_and_templates_have_no_colour_literals(path: Path) -> None:
    """Colours live in app.css; a script reads a token with getComputedStyle."""
    # Named colours (white, red) are left out: they're ordinary words in copy.
    literal = r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\("
    match = re.search(literal, path.read_text())
    assert not match, f"colour literal {match.group(0) if match else ''}"


# --- Type, space, shape and depth ----------------------------------------


def test_font_sizes_are_tokens() -> None:
    """Every font size is a --type-* token."""
    found = []
    for d in RULES:
        if d.prop == "font-size" and literal_lengths(d.value):
            found.append(where(d))
        elif d.prop == "font":
            size = d.value.split("/")[0]
            if literal_lengths(size):
                found.append(where(d))
    assert not found, "use a --type-* token: " + "; ".join(found)


def test_spacing_is_tokens() -> None:
    """Margins, paddings and gaps come from the --space-* scale."""
    found = [
        where(d) for d in RULES if SPACING_PROPERTIES.match(d.prop) and literal_lengths(d.value)
    ]
    assert not found, "use a --space-* token: " + "; ".join(found)


def test_radii_are_tokens() -> None:
    """Every corner is a --radius-* token."""
    found = [
        where(d)
        for d in RULES
        if d.prop.startswith("border") and "radius" in d.prop and literal_lengths(d.value)
    ]
    assert not found, "use a --radius-* token: " + "; ".join(found)


def test_shadows_are_tokens_or_rings() -> None:
    """A soft shadow is a --shadow-* token; a ring (no offset, no blur) may be inline."""
    ring = re.compile(r"^(?:inset )?0 0 0 \d*\.?\d+px var\(--[\w-]+\)$")
    found = []
    for d in RULES:
        if d.prop not in ("box-shadow", "text-shadow") or d.value == "none":
            continue
        parts = [part.strip() for part in re.split(r",(?![^(]*\))", d.value)]
        token = re.compile(r"var\(--shadow-[\w-]+\)")
        if not all(ring.match(part) or token.fullmatch(part) for part in parts):
            found.append(where(d))
    assert not found, "use a --shadow-* token: " + "; ".join(found)


# --- Mobile first -----------------------------------------------------------


def test_wider_screens_add_rather_than_narrow_ones_take_away() -> None:
    """The base styles are the phone's: a media query adds min-width, never max-width."""
    found = sorted(
        {at for d in DECLARATIONS for at in d.context if re.search(r"max-(?:device-)?width", at)}
    )
    assert not found, "write the phone's styles first, then add min-width: " + "; ".join(found)


# --- Limits --------------------------------------------------------------


def test_colour_tokens_are_limited() -> None:
    """Few colours, each with a job. A new one replaces one, or makes the case in DESIGN.md."""
    assert len(family("colour")) <= MAX_COLOURS, [t.name for t in family("colour")]


def test_type_sizes_are_limited() -> None:
    """A short type scale."""
    assert len(family("type")) <= MAX_TYPE_SIZES, [t.name for t in family("type")]


def test_spacing_tokens_are_the_shared_scale() -> None:
    """Every --space-* token is a step of the shared 4px scale, with its shared name."""
    wrong = [f"{t.name}: {t.value}" for t in family("space") if SPACE_SCALE.get(t.name) != t.value]
    assert not wrong, wrong


def test_radii_and_shadows_are_limited() -> None:
    """A few corners and a few depths."""
    assert len(family("radius")) <= MAX_RADII, [t.name for t in family("radius")]
    assert len(family("shadow")) <= MAX_SHADOWS, [t.name for t in family("shadow")]


# --- Nothing dead, nothing missing -----------------------------------------


def test_every_token_is_used() -> None:
    """A token nothing reads is a decision nobody made."""
    readers = CSS + SOURCES
    unused = [
        name
        for name in TOKENS
        if not re.search(rf"var\({re.escape(name)}\b|[\"']{re.escape(name)}[\"']", readers)
    ]
    assert not unused, "remove unused tokens: " + ", ".join(unused)


def test_every_token_read_is_declared() -> None:
    """A var() naming no token is invalid, so the browser silently drops the declaration."""
    read = set(re.findall(r"var\((--[\w-]+)", CSS))
    undeclared = sorted(read - set(TOKENS))
    assert not undeclared, "declare these on :root, or use a token that is: " + ", ".join(
        undeclared
    )


def test_every_class_is_used() -> None:
    """No dead CSS: every class in app.css is put on an element somewhere."""
    unused = sorted(
        name
        for name in stylesheet.class_names(CSS)
        if not name.startswith("ds-") and name not in ADDED_BY_FRAMEWORKS and not is_used(name)
    )
    assert not unused, "remove dead CSS: " + ", ".join(unused)


def design_page_source() -> str:
    """The design page's templates."""
    folder = BASE / "apps" / "design" / "templates"
    return "\n".join(path.read_text() for path in sorted(folder.rglob("*.html")))


def test_every_component_and_state_is_on_the_design_page() -> None:
    """The design page shows every component and every modifier of it.

    A component that can't be shown is named in apps/design/conf.py with
    the reason.
    """
    page = design_page_source()
    missing = []
    for name in sorted(stylesheet.class_names(CSS)):
        block = name.split("__")[0].split("--")[0]
        if block in NOT_ON_PAGE:
            continue
        if "__" in name and "--" not in name:
            continue
        if not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", page):
            missing.append(name)
    assert not missing, "show these on the design page: " + ", ".join(missing)


def test_classes_left_off_the_design_page_exist() -> None:
    """An excuse in apps/design/conf.py for a component that's gone is itself dead."""
    blocks = {name.split("__")[0].split("--")[0] for name in stylesheet.class_names(CSS)}
    stale = sorted(set(NOT_ON_PAGE) - blocks)
    assert not stale, stale


def test_the_design_page_uses_only_real_classes() -> None:
    """A class on the design page that app.css doesn't define shows nothing true."""
    page = design_page_source()
    used: set[str] = set()
    for attribute in re.findall(r'class="([^"{]*)"', page):
        used.update(attribute.split())
    unknown = sorted(used - stylesheet.class_names(CSS))
    assert not unknown, "remove from the design page, or add to app.css: " + ", ".join(unknown)
