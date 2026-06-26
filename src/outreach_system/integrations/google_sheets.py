from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Protocol

import gspread
from google.oauth2.service_account import Credentials

from outreach_system.config import Settings
from outreach_system.models import Contact, EmailState, StoredContact

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CONTACTS_SHEET_NAME = "Contactos"
WEBHOOK_EVENTS_SHEET_NAME = "WebhookEvents"


class ContactRepository(Protocol):
    def get_existing_contact_ids(self) -> set[str]: ...

    def upsert_new_contacts(self, contacts: list[Contact]) -> tuple[int, int]: ...

    def get_pending_contacts(self, limit: int | None = None) -> list[StoredContact]: ...

    def mark_as_processing(self, row_index: int) -> None: ...

    def mark_as_sent(self, row_index: int, resend_id: str) -> None: ...

    def mark_as_failed(self, row_index: int, error_message: str) -> None: ...

    def mark_as_invalid(self, row_index: int) -> None: ...

    def update_state_by_resend_id(self, resend_id: str, state: EmailState) -> bool: ...

    def has_processed_webhook_event(self, event_id: str) -> bool: ...

    def record_processed_webhook_event(
        self,
        event_id: str,
        resend_id: str,
        event_type: str,
    ) -> None: ...


class GoogleSheetsContactRepository:
    """
    Pragmatic low-volume repository backed by Google Sheets.

    This keeps the system accessible to non-technical operators, but it is not a
    transactional datastore. Atomicity is limited; a relational database should
    become the system of record once throughput or concurrency grows.
    """

    base_headers = [
        "ID",
        "Nombre",
        "Email",
        "Teléfono",
        "Teléfono Móvil",
        "Empresa",
        "Fuente",
        "Etapa",
        "Estatus",
        "Creado en",
        "Actualizado en",
        "Email Enviado",
        "Resend ID",
        "Email Abierto",
        "Email Entregado",
        "Rebote",
        "Web",
    ]
    required_headers = [
        *base_headers,
        "Estado Email",
        "Último Error",
        "Procesando Desde",
        "Último Evento Webhook",
    ]

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._spreadsheet = None

    def get_existing_contact_ids(self) -> set[str]:
        records = self._get_contacts_values()
        if len(records) <= 1:
            return set()
        return {row[0].strip() for row in records[1:] if row and row[0].strip()}

    def upsert_new_contacts(self, contacts: list[Contact]) -> tuple[int, int]:
        worksheet = self._contacts_worksheet()
        existing_ids = self.get_existing_contact_ids()
        new_rows: list[list[str]] = []
        duplicates = 0
        for contact in contacts:
            if not contact.external_id:
                continue
            if contact.external_id in existing_ids:
                duplicates += 1
                continue
            new_rows.append(self._serialize_contact(contact))
            existing_ids.add(contact.external_id)

        if new_rows:
            worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        return len(new_rows), duplicates

    def get_pending_contacts(self, limit: int | None = None) -> list[StoredContact]:
        values = self._get_contacts_values()
        if len(values) <= 1:
            return []

        headers = values[0]
        rows: list[StoredContact] = []
        sent_states = {
            EmailState.SENT.value,
            EmailState.DELIVERED.value,
            EmailState.OPENED.value,
            EmailState.BOUNCED.value,
        }
        stale_before = datetime.now(self._settings.timezone) - timedelta(
            minutes=self._settings.processing_stale_after_minutes
        )

        for row_index, row in enumerate(values[1:], start=2):
            row_dict = self._row_to_dict(headers, row)
            state = self._get_row_state(row_dict)
            resend_id = row_dict.get("Resend ID") or None
            processing_started_at = self._parse_datetime(row_dict.get("Procesando Desde"))
            is_stale_processing = (
                state == EmailState.PROCESSING.value
                and processing_started_at is not None
                and processing_started_at < stale_before
            )
            if state in sent_states:
                continue
            if state == EmailState.INVALID.value:
                continue
            if state == EmailState.PROCESSING.value and not is_stale_processing:
                continue
            if not (row_dict.get("Email") or "").strip():
                continue

            rows.append(
                StoredContact(
                    external_id=row_dict.get("ID", "").strip(),
                    name=row_dict.get("Nombre") or None,
                    email=row_dict.get("Email") or None,
                    phone=row_dict.get("Teléfono") or None,
                    mobile_phone=row_dict.get("Teléfono Móvil") or None,
                    company=row_dict.get("Empresa") or None,
                    source=row_dict.get("Fuente") or None,
                    stage=row_dict.get("Etapa") or None,
                    status=row_dict.get("Estatus") or None,
                    created_at=self._parse_datetime(row_dict.get("Creado en")),
                    updated_at=self._parse_datetime(row_dict.get("Actualizado en")),
                    website=row_dict.get("Web") or None,
                    row_index=row_index,
                    email_state=EmailState(self._get_row_state(row_dict)),
                    resend_id=resend_id,
                    last_error=row_dict.get("Último Error") or None,
                    processing_started_at=processing_started_at,
                    email_opened=(row_dict.get("Email Abierto") == "Sí"),
                    email_delivered=(row_dict.get("Email Entregado") == "Sí"),
                    email_bounced=(row_dict.get("Rebote") == "Sí"),
                )
            )
            if limit is not None and len(rows) >= limit:
                break
        return rows

    def mark_as_processing(self, row_index: int) -> None:
        self._update_contact_cells(
            row_index,
            {
                "Estado Email": EmailState.PROCESSING.value,
                "Procesando Desde": datetime.now(self._settings.timezone).isoformat(),
                "Último Error": "",
            },
        )

    def mark_as_sent(self, row_index: int, resend_id: str) -> None:
        self._update_contact_cells(
            row_index,
            {
                "Email Enviado": "Sí",
                "Estado Email": EmailState.SENT.value,
                "Resend ID": resend_id,
                "Procesando Desde": "",
                "Último Error": "",
            },
        )

    def mark_as_failed(self, row_index: int, error_message: str) -> None:
        self._update_contact_cells(
            row_index,
            {
                "Email Enviado": "No",
                "Estado Email": EmailState.FAILED.value,
                "Procesando Desde": "",
                "Último Error": error_message[:250],
            },
        )

    def mark_as_invalid(self, row_index: int) -> None:
        self._update_contact_cells(
            row_index,
            {
                "Email Enviado": "Inválido",
                "Estado Email": EmailState.INVALID.value,
            },
        )

    def update_state_by_resend_id(self, resend_id: str, state: EmailState) -> bool:
        values = self._get_contacts_values()
        if len(values) <= 1:
            return False
        headers = values[0]
        resend_col = headers.index("Resend ID")
        for row_index, row in enumerate(values[1:], start=2):
            current = row[resend_col].strip() if len(row) > resend_col else ""
            if current != resend_id:
                continue
            updates = {"Estado Email": state.value}
            if state == EmailState.OPENED:
                updates["Email Abierto"] = "Sí"
            if state == EmailState.DELIVERED:
                updates["Email Entregado"] = "Sí"
            if state == EmailState.BOUNCED:
                updates["Rebote"] = "Sí"
            self._update_contact_cells(row_index, updates)
            return True
        return False

    def has_processed_webhook_event(self, event_id: str) -> bool:
        worksheet = self._webhook_events_worksheet()
        values = worksheet.get_all_values()
        if len(values) <= 1:
            return False
        return any(len(row) > 0 and row[0] == event_id for row in values[1:])

    def record_processed_webhook_event(
        self,
        event_id: str,
        resend_id: str,
        event_type: str,
    ) -> None:
        worksheet = self._webhook_events_worksheet()
        worksheet.append_row(
            [
                event_id,
                resend_id,
                event_type,
                datetime.now(self._settings.timezone).isoformat(),
            ],
            value_input_option="USER_ENTERED",
        )

    def save_scraper_leads(self, leads: list[dict[str, str]]) -> int:
        worksheet = self._contacts_worksheet()
        values = worksheet.get_all_values()
        headers = values[0] if values else self.required_headers
        phone_col = headers.index("Teléfono")
        existing_phones = {
            row[phone_col].strip()
            for row in values[1:]
            if len(row) > phone_col and row[phone_col].strip()
        }
        new_rows: list[list[str]] = []
        today = datetime.now(self._settings.timezone).date().isoformat()
        for lead in leads:
            phone = lead.get("telefono", "").strip()
            if not phone or phone in existing_phones:
                continue
            new_rows.append(
                [
                    f"scraper-{phone}",
                    lead.get("nombre", ""),
                    lead.get("email", ""),
                    phone,
                    "",
                    lead.get("nombre", ""),
                    "Google Maps",
                    "",
                    "",
                    today,
                    today,
                    "No",
                    "",
                    "No",
                    "No",
                    "No",
                    lead.get("website", ""),
                    EmailState.PENDING.value,
                    "",
                    "",
                    "",
                ]
            )
            existing_phones.add(phone)
        if new_rows:
            worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        return len(new_rows)

    def get_rows_needing_email_enrichment(self) -> tuple[list[dict[str, str]], set[str]]:
        values = self._get_contacts_values()
        if len(values) <= 1:
            return [], set()
        headers = values[0]
        email_idx = headers.index("Email")
        web_idx = headers.index("Web")
        existing_emails = {
            row[email_idx].strip().lower()
            for row in values[1:]
            if len(row) > email_idx and row[email_idx].strip()
        }
        pending: list[dict[str, str]] = []
        for row_index, row in enumerate(values[1:], start=2):
            email = row[email_idx].strip() if len(row) > email_idx else ""
            website = row[web_idx].strip() if len(row) > web_idx else ""
            if email or not website:
                continue
            row_dict = self._row_to_dict(headers, row)
            row_dict["_row_index"] = str(row_index)
            pending.append(row_dict)
        return pending, existing_emails

    def update_email_for_row(self, row_index: int, email: str) -> None:
        self._update_contact_cells(row_index, {"Email": email})

    def _serialize_contact(self, contact: Contact) -> list[str]:
        return [
            contact.external_id,
            contact.name or "",
            str(contact.email or ""),
            contact.phone or "",
            contact.mobile_phone or "",
            contact.company or "",
            contact.source or "EasyBroker",
            contact.stage or "",
            contact.status or "",
            contact.created_at.isoformat() if contact.created_at else "",
            contact.updated_at.isoformat() if contact.updated_at else "",
            "No",
            "",
            "No",
            "No",
            "No",
            contact.website or "",
            EmailState.PENDING.value,
            "",
            "",
            "",
        ]

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _get_row_state(self, row_dict: dict[str, str]) -> str:
        explicit = (row_dict.get("Estado Email") or "").strip()
        if explicit:
            return explicit
        sent_value = (row_dict.get("Email Enviado") or "").strip()
        if sent_value == "Sí":
            return EmailState.SENT.value
        if sent_value == "Inválido":
            return EmailState.INVALID.value
        return EmailState.PENDING.value

    def _update_contact_cells(self, row_index: int, updates: dict[str, str]) -> None:
        worksheet = self._contacts_worksheet()
        headers = worksheet.row_values(1)
        batch_updates = []
        for key, value in updates.items():
            col_index = headers.index(key) + 1
            batch_updates.append(
                {
                    "range": gspread.utils.rowcol_to_a1(row_index, col_index),
                    "values": [[value]],
                }
            )
        worksheet.batch_update(batch_updates)

    def _get_contacts_values(self) -> list[list[str]]:
        return self._contacts_worksheet().get_all_values()

    def _row_to_dict(self, headers: list[str], row: list[str]) -> dict[str, str]:
        padded = row + [""] * max(0, len(headers) - len(row))
        return dict(zip(headers, padded, strict=False))

    def _client(self) -> gspread.Client:
        creds = Credentials.from_service_account_info(
            self._settings.google_service_account_info,
            scopes=SCOPES,
        )
        return gspread.authorize(creds)

    def _spreadsheet_handle(self):
        if self._spreadsheet is None:
            self._spreadsheet = self._client().open_by_key(self._settings.google_spreadsheet_id)
        return self._spreadsheet

    def _contacts_worksheet(self):
        return self._ensure_worksheet(CONTACTS_SHEET_NAME, self.required_headers)

    def _webhook_events_worksheet(self):
        return self._ensure_worksheet(
            WEBHOOK_EVENTS_SHEET_NAME,
            ["Event ID", "Resend ID", "Event Type", "Processed At"],
        )

    def _ensure_worksheet(self, title: str, headers: list[str]):
        spreadsheet = self._spreadsheet_handle()
        try:
            worksheet = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=title, rows=5000, cols=len(headers))
            worksheet.append_row(headers)
            return worksheet

        current_headers = worksheet.row_values(1)
        if not current_headers:
            worksheet.append_row(headers)
            return worksheet
        missing = [header for header in headers if header not in current_headers]
        if missing:
            updated_headers = current_headers + missing
            worksheet.update("1:1", [updated_headers])
        return worksheet
