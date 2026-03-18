"""Envio de notificações por email usando Gmail SMTP."""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Sequence
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from reclame_aqui_bot.exceptions import EmailError
from reclame_aqui_bot.models import Complaint

logger = logging.getLogger(__name__)

_SMTP_SERVER = "smtp.gmail.com"
_SMTP_PORT = 587


class GmailNotifier:
    """Envia emails em HTML via Gmail SMTP usando uma senha de aplicativo."""

    def __init__(self, *, user: str, app_password: str) -> None:
        self._user = user
        self._app_password = app_password

    def send_complaint_alert(
        self,
        complaints: Sequence[Complaint],
        *,
        recipients: Sequence[str],
        company_name: str,
    ) -> None:
        """Envia o alerta de reclamações novas para os destinatários."""
        count = len(complaints)
        subject = f"[Reclame Aqui] {count} nova(s) reclamação(ões) sem resposta"
        html_body = _render_complaint_email(complaints, company_name)
        self._send(subject=subject, html_body=html_body, recipients=recipients)

    def send_error_alert(
        self,
        error_message: str,
        *,
        recipient: str,
        component: str = "bot",
    ) -> None:
        """Envia um alerta de erro para o destinatário técnico."""
        subject = "[Reclame Aqui] Falha na execução do bot"
        html_body = _render_error_email(error_message, component)
        self._send(subject=subject, html_body=html_body, recipients=[recipient])

    def _send(
        self,
        *,
        subject: str,
        html_body: str,
        recipients: Sequence[str],
    ) -> None:
        if not recipients:
            raise EmailError("Lista de destinatários vazia")

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self._user
        message["To"] = ", ".join(recipients)
        message.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(_SMTP_SERVER, _SMTP_PORT) as server:
                server.starttls()
                server.login(self._user, self._app_password)
                server.sendmail(self._user, list(recipients), message.as_string())
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailError(f"Falha ao enviar email via SMTP: {exc}") from exc

        logger.info("Email enviado para %d destinatário(s): %s", len(recipients), subject)


def _render_complaint_email(complaints: Sequence[Complaint], company_name: str) -> str:
    items_html = "\n".join(
        _render_complaint_card(i, c) for i, c in enumerate(complaints, start=1)
    )
    generated_at = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""\
<!DOCTYPE html>
<html lang="pt-BR">
  <body style="font-family: Arial, sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; color: #333;">
    <h2 style="color: #d9534f; margin-bottom: 8px;">Novas reclamações na {company_name}</h2>
    <p>Foram encontradas <strong>{len(complaints)}</strong> reclamação(ões) sem resposta no Reclame Aqui:</p>
    {items_html}
    <hr style="border: none; border-top: 1px solid #eee; margin-top: 24px;">
    <p style="color: #999; font-size: 12px;">Verificação realizada em {generated_at}.</p>
  </body>
</html>
"""


def _render_complaint_card(index: int, complaint: Complaint) -> str:
    date_label = complaint.date or "não informada"
    return f"""\
<div style="border-left: 4px solid #d9534f; padding: 12px 16px; margin-bottom: 16px; background: #fdf7f7;">
  <div style="font-weight: bold; font-size: 16px; color: #333;">{index}. {complaint.title}</div>
  <div style="color: #666; font-size: 14px; margin-top: 6px;">Data: {date_label}</div>
  <div style="margin-top: 8px;">
    <a href="{complaint.link}" style="color: #d9534f; text-decoration: none; font-weight: 500;">
      Ver reclamação completa &raquo;
    </a>
  </div>
</div>
"""


def _render_error_email(error_message: str, component: str) -> str:
    timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    return f"""\
<!DOCTYPE html>
<html lang="pt-BR">
  <body style="font-family: Arial, sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; color: #333;">
    <h2 style="color: #d9534f;">Falha na execução do bot</h2>
    <p>O bot encontrou um erro durante a execução. Os detalhes estão abaixo.</p>
    <div style="background: #f5f5f5; padding: 16px; border-radius: 4px; margin-top: 16px;">
      <div><strong>Componente:</strong> {component}</div>
      <div><strong>Data/Hora:</strong> {timestamp}</div>
      <div style="margin-top: 12px;"><strong>Erro:</strong></div>
      <pre style="background: white; padding: 12px; border: 1px solid #ddd; overflow-x: auto; white-space: pre-wrap;">{error_message}</pre>
    </div>
    <p style="color: #999; font-size: 12px; margin-top: 24px;">Verifique <code>logs/bot.log</code> para mais detalhes.</p>
  </body>
</html>
"""
