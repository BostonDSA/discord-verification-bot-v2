import os
import secrets
import smtplib
import time
from email.mime.text import MIMEText

CODE_TTL = 600  # 10 minutes
MAX_ATTEMPTS = 5

# In-memory store: discord_id -> {code, email, expires_at, attempts}
_pending: dict = {}


def generate_and_send(discord_id: str, email: str):
    """Send a 6-digit verification code to the given email address."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    _pending[discord_id] = {
        "code": code,
        "email": email,
        "expires_at": time.time() + CODE_TTL,
        "attempts": 0,
    }

    msg = MIMEText(
        f"Your Boston DSA Discord verification code is: {code}\n\n"
        "This code expires in 10 minutes. If you didn't request this, you can ignore this email."
    )
    msg["Subject"] = "Boston DSA Discord Verification"
    msg["From"] = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER"))
    msg["To"] = email

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as smtp:
        smtp.starttls()
        smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        smtp.send_message(msg)


def verify_code(discord_id: str, code: str) -> tuple[bool, str | None]:
    """
    Validates a pending verification code.
    Returns (True, email) on success, (False, None) otherwise.
    Consumes the pending entry on success.
    """
    pending = _pending.get(discord_id)
    if not pending:
        return False, None
    if time.time() > pending["expires_at"]:
        del _pending[discord_id]
        return False, None

    pending["attempts"] += 1
    if pending["attempts"] > MAX_ATTEMPTS:
        del _pending[discord_id]
        return False, None

    if pending["code"] != code:
        return False, None

    email = pending["email"]
    del _pending[discord_id]
    return True, email


def has_pending(discord_id: str) -> bool:
    pending = _pending.get(discord_id)
    if not pending:
        return False
    if time.time() > pending["expires_at"]:
        del _pending[discord_id]
        return False
    return True
