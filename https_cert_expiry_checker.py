#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
#     "colorlog",
#     "python-http-client",
#     "requests",
#     "sendgrid",
#     "jinja2",
# ]
# ///

__author__ = "Wellington Ozorio <wozorio@duck.com>"

import dataclasses
import os
import re
import socket
import ssl
import sys
from datetime import datetime, timedelta, timezone

import click
import requests
from jinja2 import Template
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

EMAIL_ADDRESS_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

EMAIL_TEMPLATE = Template("""
<p>Dear Engineer,</p>
<p>This is to notify you that the TLS certificate for <b>{{ domain }}</b> is expiring on {{ cert_expiry_date }}.</p>
<p>Please, ensure that the certificate is renewed in a timely fashion.
There are {{ days_before_cert_expires }} days remaining.</p>
<p>Sincerely yours,</p>
<p>DevOps Team</p>
""")


@dataclasses.dataclass(frozen=True)
class Email:
    """Represent the properties of an email."""

    sender: str
    recipients: list[str]
    subject: str


def validate_email_addresses(value: str) -> list[str]:
    """Click custom parameter type to validate the format of provided email addresses."""
    emails = value.split(",")
    for email in emails:
        validate_email_address(email)
    return emails


@click.command()
@click.argument("domain")
@click.argument("sender")
@click.argument("recipients", type=validate_email_addresses)
@click.option("--threshold", default=60, type=int, help="days before expiry to notify (default: 60)")
def main(domain: str, sender: str, recipients: list[str], threshold: int) -> None:
    """Check the expiration date of HTTPS certificates and notify engineers."""
    validate_email_address(sender)

    check_sendgrid_api_key_env_var()

    check_domain(domain)

    now = datetime.now(tz=timezone.utc)
    cert_expiry_date = get_cert_expiry_date(domain)
    days_before_cert_expires = (cert_expiry_date - now).days

    if (cert_expiry_date - now) > timedelta(days=threshold):
        log(f"Nothing to worry, the TLS certificate for {domain} is expiring only in {days_before_cert_expires} days")
        return

    log(f"The TLS certificate for {domain} is expiring in {days_before_cert_expires} days")

    send_email(
        domain,
        Email(sender=sender, recipients=recipients, subject=f"TLS certificate for {domain} about to expire"),
        cert_expiry_date,
        days_before_cert_expires,
    )


def log(message: str) -> None:
    """Write a message to stderr."""
    click.echo(message, err=True)


def validate_email_address(email_address: str) -> None:
    """Validate whether an email address has a valid format."""
    match = EMAIL_ADDRESS_PATTERN.match(email_address)

    if not match:
        log(f"Email address format {email_address} is not valid")
        sys.exit(1)


def check_sendgrid_api_key_env_var() -> None:
    """Check whether the environment variable with Sendgrid API key is set."""
    if "SENDGRID_API_KEY" not in os.environ:
        log("SENDGRID_API_KEY environment variable is not set")
        sys.exit(1)


def check_domain(domain: str) -> None:
    """Check the provided domain."""
    response = requests.get("https://" + domain, allow_redirects=True, timeout=5)
    response.raise_for_status()


def get_cert_expiry_date(domain: str, port: int = 443) -> datetime:
    """Get the expiration date of the SSL certificate."""
    context = ssl.create_default_context()
    with socket.create_connection((domain, port)) as sock, context.wrap_socket(sock, server_hostname=domain) as ssock:
        cert = ssock.getpeercert()
        return datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def send_email(domain: str, email: Email, cert_expiry_date: datetime, days_before_cert_expires: int) -> None:
    """Send notification email through SendGrid API."""
    log("Sending notification via e-mail")
    message = Mail(
        from_email=email.sender,
        to_emails=email.recipients,
        subject=email.subject,
        html_content=EMAIL_TEMPLATE.render(
            domain=domain,
            cert_expiry_date=cert_expiry_date,
            days_before_cert_expires=days_before_cert_expires,
        ),
    )
    sendgrid = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    response = sendgrid.send(message)
    log(f"Email sent successfully (status code: {response.status_code})")


if __name__ == "__main__":
    main()
