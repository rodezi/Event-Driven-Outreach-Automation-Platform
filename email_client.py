from collections.abc import Callable

from outreach_system.config import get_settings
from outreach_system.integrations.google_sheets import GoogleSheetsContactRepository
from outreach_system.integrations.resend import ResendEmailClient
from outreach_system.models import StoredContact


def send_single_email(row: dict, from_email: str) -> str | None:
    del from_email
    client = ResendEmailClient(get_settings())
    contact = StoredContact.model_validate(
        {
            "external_id": row.get("ID", row.get("external_id", "")),
            "name": row.get("Nombre", row.get("name")),
            "email": row.get("Email", row.get("email")),
            "phone": row.get("Teléfono", row.get("phone")),
        }
    )
    result = client.send_email(contact)
    return result.resend_id


def send_all_with_delay(
    rows: list[dict],
    on_sent_callback: Callable[[dict, str, str], None] | None = None,
) -> tuple[int, int]:
    settings = get_settings()
    client = ResendEmailClient(settings)
    repository = GoogleSheetsContactRepository(settings)
    sent = 0
    failed = 0
    sender = settings.resend_from_emails[0]

    for index, row in enumerate(rows):
        contact = StoredContact.model_validate(
            {
                "external_id": row.get("ID", row.get("external_id", "")),
                "name": row.get("Nombre", row.get("name")),
                "email": row.get("Email", row.get("email")),
                "phone": row.get("Teléfono", row.get("phone")),
                "row_index": row.get("_row_index", row.get("row_index")),
                "email_state": row.get("Estado Email", "pending"),
            }
        )
        if contact.row_index is not None:
            repository.mark_as_processing(contact.row_index)
        try:
            result = client.send_email(contact)
        except Exception:
            failed += 1
            if contact.row_index is not None:
                repository.mark_as_failed(contact.row_index, "Legacy wrapper send failure.")
        else:
            if result.resend_id:
                sent += 1
                if on_sent_callback:
                    on_sent_callback(row, result.resend_id, sender)
        if index < len(rows) - 1:
            client.wait_before_next_send()
    return sent, failed
