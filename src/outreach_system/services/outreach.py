from __future__ import annotations

import logging

from outreach_system.exceptions import EmailDeliveryError
from outreach_system.integrations.google_sheets import ContactRepository
from outreach_system.integrations.resend import ResendEmailClient
from outreach_system.models import EmailState, ExecutionSummary

logger = logging.getLogger(__name__)


class OutreachService:
    def __init__(self, repository: ContactRepository, email_client: ResendEmailClient) -> None:
        self._repository = repository
        self._email_client = email_client

    def send_pending_emails(self, *, max_emails: int) -> ExecutionSummary:
        summary = ExecutionSummary(max_emails=max_emails)
        pending = self._repository.get_pending_contacts(limit=max_emails)
        summary.pending_contacts = len(pending)
        seen_contact_ids: set[str] = set()

        for index, contact in enumerate(pending):
            if contact.external_id in seen_contact_ids:
                continue
            seen_contact_ids.add(contact.external_id)
            summary.emails_attempted += 1

            if contact.email_state in {
                EmailState.SENT,
                EmailState.DELIVERED,
                EmailState.OPENED,
                EmailState.BOUNCED,
            }:
                continue

            if contact.row_index is None:
                continue

            if contact.email is None:
                self._repository.mark_as_invalid(contact.row_index)
                summary.email_failures += 1
                continue

            self._repository.mark_as_processing(contact.row_index)
            try:
                result = self._email_client.send_email(contact)
            except EmailDeliveryError as exc:
                self._repository.mark_as_failed(contact.row_index, str(exc))
                summary.email_failures += 1
                logger.exception("Email delivery failed for contact=%s", contact.external_id)
            else:
                if result.state == EmailState.SENT and result.resend_id:
                    self._repository.mark_as_sent(contact.row_index, result.resend_id)
                    summary.emails_sent += 1
                else:
                    self._repository.mark_as_failed(
                        contact.row_index,
                        result.error_message or "Unknown email send failure.",
                    )
                    summary.email_failures += 1

            if index < len(pending) - 1:
                self._email_client.wait_before_next_send()

        return summary
