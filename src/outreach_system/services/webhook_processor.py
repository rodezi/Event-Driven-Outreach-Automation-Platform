from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass

from outreach_system.config import Settings
from outreach_system.exceptions import WebhookVerificationError
from outreach_system.integrations.google_sheets import ContactRepository
from outreach_system.models import EmailState, ResendWebhookEvent

logger = logging.getLogger(__name__)


@dataclass
class WebhookHeaders:
    svix_id: str | None
    svix_timestamp: str | None
    svix_signature: str | None


class WebhookProcessor:
    state_map = {
        "email.sent": EmailState.SENT,
        "email.delivered": EmailState.DELIVERED,
        "email.opened": EmailState.OPENED,
        "email.bounced": EmailState.BOUNCED,
    }

    def __init__(self, settings: Settings, repository: ContactRepository) -> None:
        self._settings = settings
        self._repository = repository

    def verify_signature(self, payload: bytes, headers: WebhookHeaders) -> None:
        secret = (self._settings.resend_webhook_secret or "").strip()
        if not secret:
            return
        if not (headers.svix_id and headers.svix_timestamp and headers.svix_signature):
            raise WebhookVerificationError("Missing Svix webhook headers.")

        try:
            timestamp = int(headers.svix_timestamp)
        except ValueError as exc:
            raise WebhookVerificationError("Invalid Svix timestamp.") from exc

        if abs(time.time() - timestamp) > self._settings.webhook_timestamp_tolerance_seconds:
            raise WebhookVerificationError("Webhook timestamp is outside the allowed window.")

        secret_bytes = self._decode_secret(secret)
        message = (
            f"{headers.svix_id}.{headers.svix_timestamp}.{payload.decode('utf-8')}"
        ).encode()
        computed = base64.b64encode(
            hmac.new(secret_bytes, message, hashlib.sha256).digest()
        ).decode()
        candidates = [item.split(",", 1)[-1] for item in headers.svix_signature.split()]
        if not any(hmac.compare_digest(computed, candidate) for candidate in candidates):
            raise WebhookVerificationError("Invalid webhook signature.")

    def process_event(self, event: ResendWebhookEvent, event_id: str | None = None) -> bool:
        if not event.supported:
            logger.info("Ignoring unsupported webhook event type=%s", event.type)
            return False

        if event_id and self._repository.has_processed_webhook_event(event_id):
            logger.info("Ignoring duplicate webhook event id=%s", event_id)
            return True

        state = self.state_map[event.type]
        updated = self._repository.update_state_by_resend_id(event.resend_id, state)
        if event_id:
            self._repository.record_processed_webhook_event(
                event_id,
                event.resend_id,
                event.type,
            )
        return updated

    def _decode_secret(self, secret: str) -> bytes:
        raw_secret = secret.removeprefix("whsec_")
        try:
            return base64.b64decode(raw_secret)
        except Exception:
            return raw_secret.encode("utf-8")
