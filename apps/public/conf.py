"""The site's links and whose copyright it is.

The website's pages end with them in a footer, and the app shows them on
its account page (DESIGN.md, "The website has a footer; the app has its
links"); the tags in ``templatetags/site_footer.py`` draw them. Set once by
the project template from its answers; edit freely.
"""

# The footer's copyright line: "© <this year> <holder>. All rights reserved."
COPYRIGHT_HOLDER = "Hugo Rodger-Brown"

# The links, in order: (label, URL name). A "#fragment" after the
# name links to a part of that page, as "Use with Claude" does: the help
# page's steps for Claude and ChatGPT (DESIGN.md, "The front page").
# Keep the terms and privacy notice: a site without them isn't legit.
LINKS: list[tuple[str, str]] = [
    ("Home", "public:home"),
    ("Help", "public:help"),
    ("Use with Claude", "public:help#use-with-ai"),
    ("Terms", "public:terms"),
    ("Privacy", "public:privacy"),
]
