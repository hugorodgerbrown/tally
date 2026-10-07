"""The terms, privacy notice and help as Markdown, for readers that aren't browsers.

The MCP tools serve these pages so an assistant can answer "what do you
keep about me?" from the same words the website shows. Each page's body is
one template (``public/_<name>_body.html``) that both the page and this
module render, so the two never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from apps.pwa.context_processors import identity


@dataclass(frozen=True)
class Page:
    """A public page whose words can be read outside a browser."""

    title: str
    url_name: str
    template: str


PAGES = {
    "terms": Page("Terms of service", "public:terms", "public/_terms_body.html"),
    "privacy": Page("Privacy notice", "public:privacy", "public/_privacy_body.html"),
    "help": Page("Help", "public:help", "public/_help_body.html"),
}


def page_as_markdown(name: str) -> dict[str, str]:
    """Return a page's title, absolute URL and body (``markdown``)."""
    page = PAGES[name]
    html = render_to_string(page.template, {"pwa": identity()})
    return {
        "title": page.title,
        "url": urljoin(settings.SITE_URL, reverse(page.url_name)),
        "markdown": to_markdown(html),
    }


def to_markdown(html: str) -> str:
    """Convert the small HTML the public pages use to Markdown.

    Headings, paragraphs, lists, bold and links: anything else keeps only
    its text. Relative links become absolute, against ``SITE_URL``.
    """
    parser = _MarkdownParser()
    parser.feed(html)
    parser.close()
    return parser.markdown()


class _MarkdownParser(HTMLParser):
    """Collects blocks of Markdown from the public pages' HTML."""

    _BLOCKS = {"h1": "# ", "h2": "## ", "h3": "### ", "p": "", "li": "- "}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current: list[str] | None = None
        self.href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open a block, or mark up text inside one."""
        if tag in self._BLOCKS:
            self.current = [self._BLOCKS[tag]]
        elif tag in ("strong", "b") and self.current is not None:
            self.current.append("**")
        elif tag == "a" and self.current is not None:
            self.href = dict(attrs).get("href") or ""
            self.current.append("[")

    def handle_endtag(self, tag: str) -> None:
        """Close a block, or the markup inside one."""
        if self.current is None:
            return
        if tag in self._BLOCKS:
            text = " ".join("".join(self.current).split())
            if text.strip("#- "):
                self.blocks.append(text)
            self.current = None
        elif tag in ("strong", "b"):
            self.current.append("**")
        elif tag == "a" and self.href is not None:
            self.current.append(f"]({urljoin(settings.SITE_URL, self.href)})")
            self.href = None

    def handle_data(self, data: str) -> None:
        """Keep text that sits inside a block."""
        if self.current is not None:
            self.current.append(data)

    def markdown(self) -> str:
        """Join the blocks; list items stay together, everything else is a paragraph."""
        out: list[str] = []
        for block in self.blocks:
            if out and not (block.startswith("- ") and out[-1].startswith("- ")):
                out.append("")
            out.append(block)
        return "\n".join(out) + "\n"
