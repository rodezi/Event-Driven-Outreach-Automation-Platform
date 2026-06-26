from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException, Request

from outreach_system.config import Settings, get_settings
from outreach_system.exceptions import WebhookVerificationError
from outreach_system.integrations.google_sheets import GoogleSheetsContactRepository
from outreach_system.models import ResendWebhookEvent
from outreach_system.services.webhook_processor import WebhookHeaders, WebhookProcessor

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    processor: WebhookProcessor | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    processor = processor or WebhookProcessor(
        settings,
        GoogleSheetsContactRepository(settings),
    )
    app = FastAPI(title="Event-Driven Outreach Automation Platform")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/resend")
    async def resend_webhook(
        request: Request,
        svix_id: str | None = Header(default=None, alias="svix-id"),
        svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
        svix_signature: str | None = Header(default=None, alias="svix-signature"),
    ) -> dict[str, str]:
        raw_body = await request.body()
        try:
            processor.verify_signature(
                raw_body,
                WebhookHeaders(
                    svix_id=svix_id,
                    svix_timestamp=svix_timestamp,
                    svix_signature=svix_signature,
                ),
            )
        except WebhookVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        try:
            event = ResendWebhookEvent.model_validate_json(raw_body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

        processor.process_event(event, event_id=svix_id)
        return {"status": "ok"}

    return app
