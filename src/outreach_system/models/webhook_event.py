from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ResendEventType(StrEnum):
    SENT = "email.sent"
    DELIVERED = "email.delivered"
    OPENED = "email.opened"
    BOUNCED = "email.bounced"


class ResendWebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    created_at: datetime | None = None
    email_id: str
    from_email: str | None = Field(default=None, alias="from")
    to: list[str] = Field(default_factory=list)
    subject: str | None = None


class ResendWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    data: ResendWebhookData

    @property
    def resend_id(self) -> str:
        return self.data.email_id

    @property
    def supported(self) -> bool:
        return self.type in {item.value for item in ResendEventType}
