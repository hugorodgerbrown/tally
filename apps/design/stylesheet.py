"""Reads static/css/app.css: its tokens and its declarations.

The design page lists the tokens from here, and tests/test_design.py holds
the stylesheet to the rules in DESIGN.md with the same reading, so the page
and the rules never disagree about what the stylesheet says.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Token families by name. A colour token is any other token whose value is a
# colour; the rest (layout sizes, font stacks) are "other".
FAMILY_PREFIXES = {
    "--type-": "type",
    "--space-": "space",
    "--radius-": "radius",
    "--shadow-": "shadow",
}

COLOUR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(|"
    r"\b(?:white|black|red|green|blue|grey|gray|orange|yellow|purple|pink)\b",
)


def stylesheet_path() -> Path:
    """Where the app's one stylesheet lives."""
    return Path(settings.BASE_DIR) / "static" / "css" / "app.css"


@dataclass(frozen=True)
class Declaration:
    """One ``property: value`` in a rule.

    Attributes:
        selector: The rule's selector (``:root``, ``.button:hover``).
        context: The at-rules around it, outermost first (``@media ...``).
        prop: The property, lower-cased.
        value: The value, as written.
    """

    selector: str
    context: tuple[str, ...]
    prop: str
    value: str

    @property
    def in_root(self) -> bool:
        """Whether this declares a token: it sits in a ``:root`` rule."""
        return self.selector == ":root"


@dataclass(frozen=True)
class Token:
    """A custom property declared on ``:root``.

    Attributes:
        name: The property name, with its ``--``.
        value: Its value in the light (default) scheme.
        family: ``colour``, ``type``, ``space``, ``radius``, ``shadow`` or ``other``.
    """

    name: str
    value: str
    family: str


def strip_comments(css: str) -> str:
    """The stylesheet without its ``/* */`` comments."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _split_declarations(text: str) -> list[str]:
    """Split a block's body on the semicolons outside brackets and quotes."""
    parts: list[str] = []
    depth = 0
    quote = ""
    start = 0
    for i, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == ";" and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def parse(css: str) -> list[Declaration]:
    """Every declaration in the stylesheet, in order.

    Args:
        css: The stylesheet's source.

    Returns:
        One Declaration per ``property: value``, with its selector and the
        at-rules around it. Comma-separated selectors stay as one selector.
    """
    css = strip_comments(css)
    declarations: list[Declaration] = []
    stack: list[str] = []
    buffer = ""
    quote = ""
    depth = 0

    def flush(text: str) -> None:
        if not stack:
            return
        for part in _split_declarations(text):
            prop, sep, value = part.partition(":")
            if sep:
                declarations.append(
                    Declaration(
                        selector=" ".join(stack[-1].split()),
                        context=tuple(stack[:-1]),
                        prop=prop.strip().lower(),
                        value=" ".join(value.split()),
                    )
                )

    for char in css:
        if quote:
            buffer += char
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and char == "{":
            body, _, prelude = buffer.rpartition(";")
            flush(body)
            stack.append(prelude.strip())
            buffer = ""
            continue
        elif depth == 0 and char == "}":
            flush(buffer)
            if stack:
                stack.pop()
            buffer = ""
            continue
        buffer += char
    return declarations


def family_of(name: str, value: str) -> str:
    """The family a token belongs to, from its name or (for colours) its value."""
    for prefix, family in FAMILY_PREFIXES.items():
        if name.startswith(prefix):
            return family
    if COLOUR_LITERAL.search(value) or value == "transparent":
        return "colour"
    return "other"


def tokens(declarations: list[Declaration]) -> dict[str, Token]:
    """The tokens, by name, as the light scheme defines them.

    A dark scheme (``:root`` inside an ``@media``) redefines tokens rather
    than adding them, so the first definition of each name is the one kept.
    """
    found: dict[str, Token] = {}
    for declaration in declarations:
        if declaration.in_root and declaration.prop.startswith("--"):
            name = declaration.prop
            if name not in found:
                found[name] = Token(name, declaration.value, family_of(name, declaration.value))
    return found


def read() -> list[Declaration]:
    """Every declaration in the app's stylesheet."""
    return parse(stylesheet_path().read_text())


def class_names(css: str) -> set[str]:
    """Every class the stylesheet's selectors name."""
    names: set[str] = set()
    css = strip_comments(css)
    css = re.sub(r"url\([^)]*\)", "", css)
    for prelude in re.findall(r"([^{};]+)\{", css):
        if prelude.strip().startswith("@"):
            continue
        names.update(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", prelude))
    return names
