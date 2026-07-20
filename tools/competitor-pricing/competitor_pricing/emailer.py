from __future__ import annotations

import os
import smtplib
from datetime import date
from email.message import EmailMessage

from .config import EmailConfig


def _alerts_html(alerts: list[dict]) -> str:
    if not alerts:
        return ""
    items = "".join(f"<li>{a['text']}</li>" for a in alerts)
    return (
        '<h3 style="color:#9b2c1f">Changes since last run</h3>'
        f"<ul>{items}</ul><hr/>"
    )


def send_report_email(
    email_config: EmailConfig,
    html_body: str,
    csv_body: str,
    alerts: list[dict] | None = None,
) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")

    if not all([host, user, password, email_config.from_addr, email_config.to]):
        raise RuntimeError(
            "Email is not fully configured. Need SMTP_HOST/SMTP_USER/SMTP_PASSWORD "
            "env vars plus email.from and email.to in config.yaml."
        )

    alerts = alerts or []
    subject = f"{email_config.subject_prefix} {date.today().isoformat()}"
    if alerts:
        subject += f" — {len(alerts)} change{'s' if len(alerts) != 1 else ''}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_config.from_addr
    msg["To"] = ", ".join(email_config.to)
    msg.set_content("This report requires an HTML-capable email client.")
    msg.add_alternative(
        f"<html><body>{_alerts_html(alerts)}{html_body}</body></html>",
        subtype="html",
    )

    msg.add_attachment(
        csv_body.encode("utf-8"),
        maintype="text",
        subtype="csv",
        filename=f"competitor-pricing-{date.today().isoformat()}.csv",
    )

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
