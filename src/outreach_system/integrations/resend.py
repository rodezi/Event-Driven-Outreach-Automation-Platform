from __future__ import annotations

import logging
import random
import time
from itertools import cycle
from typing import Protocol

import resend

from outreach_system.config import Settings
from outreach_system.exceptions import EmailDeliveryError
from outreach_system.models import EmailSendResult, EmailState, StoredContact
from outreach_system.utils import mask_email

logger = logging.getLogger(__name__)


class ResendApi(Protocol):
    api_key: str | None


class ResendEmailClient:
    def __init__(
        self,
        settings: Settings,
        resend_module=resend,
        sleeper: callable | None = None,
        randomizer: callable | None = None,
    ) -> None:
        self._settings = settings
        self._resend = resend_module
        self._sleep = sleeper or time.sleep
        self._random = randomizer or random.uniform
        self._sender_pool = cycle(settings.resend_from_emails)

    def send_email(self, contact: StoredContact) -> EmailSendResult:
        if contact.email is None:
            return EmailSendResult(
                contact_id=contact.external_id,
                state=EmailState.INVALID,
                error_message="Missing or invalid email address.",
            )

        from_email = next(self._sender_pool)
        self._resend.api_key = self._settings.resend_api_key
        try:
            result = self._resend.Emails.send(
                {
                    "from": from_email,
                    "to": [str(contact.email)],
                    "reply_to": self._settings.resend_reply_to,
                    "subject": self._settings.resend_email_subject,
                    "html": self._build_email_body(contact),
                }
            )
        except Exception as exc:
            raise EmailDeliveryError(
                f"Resend send failed for {mask_email(str(contact.email))}."
            ) from exc

        resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        if not resend_id:
            raise EmailDeliveryError("Resend response did not include a message id.")
        logger.info("Email queued via Resend for %s", mask_email(str(contact.email)))
        return EmailSendResult(
            contact_id=contact.external_id,
            resend_id=str(resend_id),
            state=EmailState.SENT,
        )

    def wait_before_next_send(self) -> None:
        delay = self._random(
            self._settings.email_delay_min_seconds,
            self._settings.email_delay_max_seconds,
        )
        self._sleep(delay)

    def _build_email_body(self, contact: StoredContact) -> str:
        salutation = f"Hola, {contact.name}" if contact.name else "Hola"
        style = (
            "font-family: Georgia, serif; color: #1a1a1a; max-width: 560px; "
            "margin: auto; line-height: 1.75; font-size: 15px;"
        )
        return f"""<html><body style="{style}">
<p>{salutation}</p>
<p>Vi que su agencia tiene presencia en portales inmobiliarios y me quedé pensando
en algo que vale la pena compartirle.</p>
<p>Revisé cómo responden inmobiliarias similares en su zona, y encontré algo concreto:
la mayoría pierde entre el 40 y 60% de sus leads simplemente por tiempo de respuesta,
no por precio, ni por inventario.</p>
<p>Con las agencias con las que trabajamos, ese tiempo bajó de un promedio de 3 horas
a menos de 90 segundos.</p>
<p>Trabajamos exclusivamente con inmobiliarias en México. Conocemos los ciclos de compra
locales y los retos específicos del sector.</p>
<p>Antes de pedirle cualquier cosa: ¿le mando un video de 90 segundos donde le muestro
exactamente cómo funcionaría para su inmobiliaria?</p>
<p>Solo responda "sí" y se lo envío hoy.</p>
<p>Alex, Outreach Ops</p>
</body></html>"""
