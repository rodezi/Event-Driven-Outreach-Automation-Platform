from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from outreach_system.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {
            "EASYBROKER_API_KEY": "easybroker-test-key",
            "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
            "GOOGLE_SPREADSHEET_ID": "spreadsheet-id",
            "RESEND_API_KEY": "resend-test-key",
            "RESEND_FROM_EMAILS": ["ops@example.com", "campaign@example.com"],
            "RESEND_WEBHOOK_SECRET": "whsec_dGVzdF9zZWNyZXQ=",
            "OUTREACH_TIMEZONE": "America/Mexico_City",
            "EMAIL_DELAY_MIN_SECONDS": 1,
            "EMAIL_DELAY_MAX_SECONDS": 2,
            "LOG_LEVEL": "INFO",
        }
    )


def build_svix_signature(secret: str, payload: bytes, event_id: str, timestamp: str) -> str:
    raw_secret = base64.b64decode(secret.removeprefix("whsec_"))
    message = f"{event_id}.{timestamp}.{payload.decode('utf-8')}".encode()
    digest = hmac.new(raw_secret, message, hashlib.sha256).digest()
    return f"v1,{base64.b64encode(digest).decode()}"


@pytest.fixture
def webhook_payload() -> bytes:
    return json.dumps(
        {
            "type": "email.delivered",
            "data": {
                "email_id": "re_123",
                "to": ["lead@example.com"],
            },
        }
    ).encode("utf-8")
