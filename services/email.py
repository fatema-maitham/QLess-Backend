# services/email.py
import smtplib
from email.message import EmailMessage

from config.environment import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


def send_email(to: str, subject: str, body: str):
    # No email settings yet: show the email in the terminal so we can still test
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        print(f"\n--- EMAIL to {to} ---\nSubject: {subject}\n\n{body}\n--- END EMAIL ---\n")
        return

    message = EmailMessage()
    message["From"] = f"QLess <{SMTP_USER}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)