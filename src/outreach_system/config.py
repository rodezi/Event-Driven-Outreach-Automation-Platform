from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from outreach_system.exceptions import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    easybroker_api_key: str = Field(alias="EASYBROKER_API_KEY")
    google_service_account_json: str = Field(alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_spreadsheet_id: str = Field(alias="GOOGLE_SPREADSHEET_ID")
    resend_api_key: str = Field(alias="RESEND_API_KEY")
    resend_from_emails: Annotated[list[str], NoDecode] = Field(alias="RESEND_FROM_EMAILS")
    resend_webhook_secret: str | None = Field(
        default=None,
        alias="RESEND_WEBHOOK_SECRET",
    )
    resend_reply_to: str | None = Field(default=None, alias="RESEND_REPLY_TO")
    resend_email_subject: str = Field(
        default="La llamada que perdió hoy ya fue a la competencia",
        alias="RESEND_EMAIL_SUBJECT",
    )
    outreach_timezone: str = Field(
        default="America/Mexico_City",
        alias="OUTREACH_TIMEZONE",
    )
    email_delay_min_seconds: int = Field(default=120, alias="EMAIL_DELAY_MIN_SECONDS")
    email_delay_max_seconds: int = Field(default=180, alias="EMAIL_DELAY_MAX_SECONDS")
    easybroker_timeout_seconds: int = Field(default=30, alias="EASYBROKER_TIMEOUT_SECONDS")
    easybroker_page_limit: int = Field(default=50, alias="EASYBROKER_PAGE_LIMIT")
    easybroker_days_back: int = Field(default=0, alias="EASYBROKER_DAYS_BACK")
    easybroker_max_retries: int = Field(default=3, alias="EASYBROKER_MAX_RETRIES")
    webhook_timestamp_tolerance_seconds: int = Field(
        default=300,
        alias="WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS",
    )
    processing_stale_after_minutes: int = Field(
        default=180,
        alias="PROCESSING_STALE_AFTER_MINUTES",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")
    webhook_port: int = Field(default=8080, alias="WEBHOOK_PORT")

    @model_validator(mode="before")
    @classmethod
    def _split_from_emails(cls, values: dict) -> dict:
        raw = values.get("RESEND_FROM_EMAILS") or values.get("resend_from_emails")
        if isinstance(raw, str):
            values["RESEND_FROM_EMAILS"] = [item.strip() for item in raw.split(",") if item.strip()]
        return values

    @model_validator(mode="after")
    def _validate_ranges(self) -> Settings:
        if not self.resend_from_emails:
            raise ConfigurationError("RESEND_FROM_EMAILS must contain at least one sender.")
        if self.email_delay_min_seconds > self.email_delay_max_seconds:
            raise ConfigurationError(
                "EMAIL_DELAY_MIN_SECONDS cannot be greater than EMAIL_DELAY_MAX_SECONDS."
            )
        try:
            ZoneInfo(self.outreach_timezone)
        except Exception as exc:
            raise ConfigurationError("OUTREACH_TIMEZONE is invalid.") from exc
        return self

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.outreach_timezone)

    @property
    def google_service_account_info(self) -> dict:
        value = self.google_service_account_json.strip()
        if value.startswith("{"):
            return json.loads(value)
        path = Path(value)
        if not path.exists():
            raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_JSON path does not exist.")
        return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigurationError("Invalid application configuration.") from exc
