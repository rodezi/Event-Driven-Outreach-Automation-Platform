from __future__ import annotations

import logging
import uuid

from outreach_system.config import Settings, get_settings
from outreach_system.integrations import (
    EasyBrokerClient,
    GoogleSheetsContactRepository,
    ResendEmailClient,
)
from outreach_system.logging_config import configure_logging, set_execution_id
from outreach_system.models import ExecutionSummary
from outreach_system.services import ContactSyncService, OutreachService

logger = logging.getLogger(__name__)


def run_pipeline(max_emails: int = 100, settings: Settings | None = None) -> ExecutionSummary:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    set_execution_id(uuid.uuid4().hex[:8])

    repository = GoogleSheetsContactRepository(settings)
    sync_service = ContactSyncService(EasyBrokerClient(settings), repository)
    outreach_service = OutreachService(repository, ResendEmailClient(settings))

    sync_result = sync_service.sync()
    send_summary = outreach_service.send_pending_emails(max_emails=max_emails)
    send_summary.fetched_contacts = sync_result.fetched_contacts
    send_summary.new_contacts = sync_result.new_contacts
    send_summary.duplicates = sync_result.duplicate_contacts

    logger.info(
        "Pipeline summary fetched=%s new=%s duplicates=%s pending=%s sent=%s failed=%s",
        send_summary.fetched_contacts,
        send_summary.new_contacts,
        send_summary.duplicates,
        send_summary.pending_contacts,
        send_summary.emails_sent,
        send_summary.email_failures,
    )
    return send_summary
