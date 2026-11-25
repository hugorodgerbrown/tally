"""Background tasks for accounts: the sign-in (or sign-up) email.

Views enqueue; they never send mail themselves, so a slow mail server
can't hold a request (settings.TASKS chooses where the task runs: on a
thread of its own, apps.core.task_backends.ThreadBackend).

The address is only this task's argument, so with the thread backend it
stays in memory. A queue-backed backend would store it until the email is
sent, and the privacy notice would have to say so.

The email is written as a one-time verification code, with the link as a
shortcut, so mail apps such as Gmail recognise it and offer to copy the code
(DESIGN.md, "The sign-in email").
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.tasks import task
from django.template.loader import render_to_string

from apps.pwa import conf


def otp_token_header(code: str) -> str:
    """Return the ``OTP-Token`` header value for ``code`` (draft-goto-otp-token).

    An Internet-Draft, not a standard: it names the code and the origin that
    asked for it, so a mail client could hand the code only to this site.
    """
    url = urlsplit(settings.SITE_URL)
    default_port = {"http": 80, "https": 443}.get(url.scheme)
    port = f":{url.port}" if url.port and url.port != default_port else ""
    return f'"{code}"; origin="{url.scheme}://{url.hostname}{port}"'


@task()
def send_sign_in_email(email: str, link: str, code: str, purpose: str = "sign_in") -> None:
    """Email ``email`` its code and link, as plain text and HTML.

    ``purpose`` "sign_up" words the link for a new account (Tally).
    """
    context = {
        "signing_up": purpose == "sign_up",
        "link": link,
        "code": code,
        "minutes": settings.SIGN_IN_MAX_AGE_SECONDS // 60,
        "site_name": conf.APP_NAME,
        "brand_colour": conf.THEME_COLOUR,
    }
    subject = render_to_string("accounts/emails/sign_in_subject.txt", context).strip()
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string("accounts/emails/sign_in.txt", context),
        to=[email],
        headers={"OTP-Token": otp_token_header(code)},
    )
    html = render_to_string("accounts/emails/sign_in.html", context)
    message.attach_alternative(html, "text/html")
    message.send()
