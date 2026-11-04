import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import partial

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_sync(to: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(settings.smtp_from, [to], msg.as_string())


async def _send(to: str, subject: str, html_body: str) -> None:
    if not settings.smtp_user:
        logger.info("[MAIL-STUB] To=%s Subject=%r", to, subject)
        return
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, partial(_send_sync, to, subject, html_body))
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        raise


async def send_confirmation(to: str, user_id: str) -> None:
    html = """
<p>¡Bienvenido a <strong>ASR Quechua</strong>!</p>
<p>Tu cuenta ha sido registrada correctamente. Ya puedes iniciar sesión y empezar a transcribir audio en quechua.</p>
"""
    await _send(to, "¡Bienvenido a ASR Quechua!", html)


async def send_verification_link(to: str, token: str, link_type: str) -> None:
    link = f"{settings.frontend_url}/verify-email?token={token}&type={link_type}"
    html = f"""
<p>Haz clic en el siguiente enlace para verificar tu nuevo correo electrónico:</p>
<p><a href="{link}">Verificar correo electrónico</a></p>
<p>Si no realizaste este cambio, ignora este mensaje.</p>
"""
    await _send(to, "Verifica tu correo electrónico – ASR Quechua", html)
