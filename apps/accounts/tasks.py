"""Background tasks for accounts: the sign-in (or sign-up) email.

Views enqueue; they never send mail themselves, so a slow mail server
can't hold a request (settings.TASKS chooses where the task runs).
"""

from django.conf import settings
from django.core.mail import send_mail
from django.tasks import task
from django.template.loader import render_to_string

from apps.pwa import conf


@task()
def send_sign_in_email(email: str, link: str, code: str, purpose: str = "sign_in") -> None:
    """Email ``email`` its link and code; ``purpose`` "sign_up" words it for a new account."""
    context = {
        "signing_up": purpose == "sign_up",
        "link": link,
        "code": code,
        "minutes": settings.SIGN_IN_MAX_AGE_SECONDS // 60,
        "site_name": conf.APP_NAME,
    }
    subject = render_to_string("accounts/emails/sign_in_subject.txt", context).strip()
    body = render_to_string("accounts/emails/sign_in.txt", context)
    send_mail(subject, body, None, [email])
