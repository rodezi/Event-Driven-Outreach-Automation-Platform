from __future__ import annotations

import time

from fastapi.testclient import TestClient

from outreach_system.api.webhooks import create_app
from outreach_system.models import EmailState
from outreach_system.services.webhook_processor import WebhookProcessor
from tests.conftest import build_svix_signature


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
        del resend_id, event_type
        self.processed_ids.add(event_id)


def test_health_endpoint(settings) -> None:
    app = create_app(settings=settings, processor=WebhookProcessor(settings, FakeRepository()))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_signature_is_rejected(settings, webhook_payload) -> None:
    app = create_app(settings=settings, processor=WebhookProcessor(settings, FakeRepository()))
    client = TestClient(app)

    response = client.post(
        "/webhooks/resend",
        content=webhook_payload,
        headers={
            "svix-id": "evt_invalid",
            "svix-timestamp": str(int(time.time())),
            "svix-signature": "v1,invalid",
        },
    )

    assert response.status_code == 401


def test_duplicate_webhook_event_is_idempotent(settings, webhook_payload) -> None:
    repository = FakeRepository()
    processor = WebhookProcessor(settings, repository)
    app = create_app(settings=settings, processor=processor)
    client = TestClient(app)
    event_id = "evt_123"
    timestamp = str(int(time.time()))
    signature = build_svix_signature(
        settings.resend_webhook_secret or "",
        webhook_payload,
        event_id,
        timestamp,
    )
    headers = {
        "svix-id": event_id,
        "svix-timestamp": timestamp,
        "svix-signature": signature,
    }

    first = client.post("/webhooks/resend", content=webhook_payload, headers=headers)
    second = client.post("/webhooks/resend", content=webhook_payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert repository.updated == [("re_123", EmailState.DELIVERED)]
