from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailState(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    BOUNCED = "bounced"
    FAILED = "failed"
    INVALID = "invalid"


class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    external_id: str
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    mobile_phone: str | None = None
    company: str | None = None
    source: str | None = None
    stage: str | None = None
    status: str | None = None
    website: str | None = None


class StoredContact(Contact):
    row_index: int | None = None
    email_state: EmailState = EmailState.PENDING
    resend_id: str | None = None
    last_error: str | None = None
    processing_started_at: datetime | None = None
    email_opened: bool = False
    email_delivered: bool = False
    email_bounced: bool = False


class ContactSyncResult(BaseModel):
    fetched_contacts: int = 0
    normalized_contacts: int = 0
    new_contacts: int = 0
    duplicate_contacts: int = 0


class EmailSendResult(BaseModel):
    contact_id: str
    resend_id: str | None = None
    state: EmailState
    error_message: str | None = None


class ExecutionSummary(BaseModel):
    fetched_contacts: int = 0
    new_contacts: int = 0
    duplicates: int = 0
    pending_contacts: int = 0
    emails_attempted: int = 0
    emails_sent: int = 0
    email_failures: int = 0
    webhooks_processed: int = 0
    max_emails: int = Field(default=100, ge=1)

    @property
    def partially_failed(self) -> bool:
        return self.email_failures > 0
