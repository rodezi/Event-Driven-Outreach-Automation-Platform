from __future__ import annotations

import pytest

from outreach_system.exceptions import WebhookVerificationError
from outreach_system.models import EmailState, ResendWebhookEvent
from outreach_system.services.webhook_processor import WebhookHeaders, WebhookProcessor


class FakeRepository:
    def __init__(self) -> None:
        self.updated: list[tuple[str, EmailState]] = []
        self.processed_ids: set[str] = set()

    def update_state_by_resend_id(self, resend_id: str, state: EmailState) -> bool:
        self.updated.append((resend_id, state))
        return True

    def has_processed_webhook_event(self, event_id: str) -> bool:
        return event_id in self.processed_ids

    def record_processed_webhook_event(
        self,
        event_id: str,
        resend_id: str,
        event_type: str,
    ) -> None:
        self.processed_ids.add(event_id)


@pytest.mark.parametrize(
    ("event_type", "expected_state"),
    [
        ("email.delivered", EmailState.DELIVERED),
        ("email.opened", EmailState.OPENED),
        ("email.bounced", EmailState.BOUNCED),
    ],
)
def test_processes_supported_webhook_events(
    settings,
    event_type: str,
    expected_state: EmailState,
) -> None:
    repository = FakeRepository()
    processor = WebhookProcessor(settings, repository)
    event = ResendWebhookEvent.model_validate(
        {"type": event_type, "data": {"email_id": "re_123", "to": ["lead@example.com"]}}
    )

    updated = processor.process_event(event, event_id=f"evt-{event_type}")

    assert updated is True
    assert repository.updated == [("re_123", expected_state)]


def test_rejects_invalid_signature(settings, webhook_payload) -> None:
    processor = WebhookProcessor(settings, FakeRepository())

    with pytest.raises(WebhookVerificationError):
        processor.verify_signature(
            webhook_payload,
            WebhookHeaders(
                svix_id="evt_1",
                svix_timestamp="1700000000",
                svix_signature="v1,invalid",
            ),
        )


def test_webhook_event_processing_is_idempotent(settings) -> None:
    repository = FakeRepository()
    processor = WebhookProcessor(settings, repository)
    event = ResendWebhookEvent.model_validate(
        {"type": "email.delivered", "data": {"email_id": "re_123", "to": ["lead@example.com"]}}
    )

    first = processor.process_event(event, event_id="evt_1")
    second = processor.process_event(event, event_id="evt_1")

    assert first is True
    assert second is True
    assert repository.updated == [("re_123", EmailState.DELIVERED)]
