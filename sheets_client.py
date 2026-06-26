from outreach_system.config import get_settings
from outreach_system.integrations.google_sheets import GoogleSheetsContactRepository


def _repository() -> GoogleSheetsContactRepository:
    return GoogleSheetsContactRepository(get_settings())


HEADERS = GoogleSheetsContactRepository.required_headers


def save_contacts_to_sheet(contacts: list[dict], sheet_name: str = "Contactos") -> int:
    del sheet_name
    from outreach_system.models import Contact

    parsed = [
        Contact.model_validate(
            {
                **contact,
                "external_id": contact.get("id", contact.get("external_id", "")),
            }
        )
        for contact in contacts
    ]
    written, _ = _repository().upsert_new_contacts(parsed)
    return written


def get_pending_email_rows(sheet_name: str = "Contactos") -> list[dict]:
    del sheet_name
    return [contact.model_dump(mode="json") for contact in _repository().get_pending_contacts()]


def mark_email_sent(row_index: int, resend_id: str, sheet_name: str = "Contactos") -> None:
    del sheet_name
    _repository().mark_as_sent(row_index, resend_id)


def update_email_event(resend_id: str, event_type: str, sheet_name: str = "Contactos") -> bool:
    del sheet_name
    from outreach_system.models import EmailState

    mapping = {
        "email.sent": EmailState.SENT,
        "email.delivered": EmailState.DELIVERED,
        "email.opened": EmailState.OPENED,
        "email.bounced": EmailState.BOUNCED,
    }
    state = mapping.get(event_type)
    if state is None:
        return False
    return _repository().update_state_by_resend_id(resend_id, state)


def save_scraper_leads_to_sheet(leads: list[dict], sheet_name: str = "Contactos") -> int:
    del sheet_name
    return _repository().save_scraper_leads(leads)


def get_rows_needing_email_enrichment(sheet_name: str = "Contactos") -> tuple[list[dict], set[str]]:
    del sheet_name
    return _repository().get_rows_needing_email_enrichment()


def update_email_for_row(row_index: int, email: str, sheet_name: str = "Contactos") -> None:
    del sheet_name
    _repository().update_email_for_row(row_index, email)


def mark_email_invalid(row_index: int, sheet_name: str = "Contactos") -> None:
    del sheet_name
    _repository().mark_as_invalid(row_index)
