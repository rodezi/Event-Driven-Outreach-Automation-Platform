import os
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
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
    "Email Enviado",   # "No" / "Sí"
    "Resend ID",       # ID retornado por Resend al enviar
    "Email Abierto",   # webhook email.opened
    "Email Entregado", # webhook email.delivered
    "Rebote",          # webhook email.bounced
    "Web",             # URL del sitio web (leads del scraper)
]

CONTACT_KEYS = [
    "id",
    "name",
    "email",
    "phone",
    "mobile_phone",
    "company",
    "source",
    "stage",
    "status",
    "created_at",
    "updated_at",
]

# Mapa de tipo de evento webhook → columna del sheet
EVENT_COLUMN_MAP = {
    "email.opened":    "Email Abierto",
    "email.delivered": "Email Entregado",
    "email.bounced":   "Rebote",
}


def _get_client() -> gspread.Client:
    """
    Soporta dos formas de pasar las credenciales de Google:
      1. Ruta a un archivo JSON:   GOOGLE_SERVICE_ACCOUNT_JSON=/tmp/sa.json
         (GitHub Actions escribe el secret a un archivo temporal)
      2. Contenido JSON directo:   GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
         (útil si se prefiere evitar archivos en disco)
    """
    import json as _json
    value = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not value:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON no está definida")

    value = value.strip()
    if value.startswith("{"):
        # Es el contenido JSON directamente
        info = _json.loads(value)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # Es una ruta de archivo
        creds = Credentials.from_service_account_file(value, scopes=SCOPES)

    return gspread.authorize(creds)


def _open_worksheet(sheet_name: str = "Contactos") -> gspread.Worksheet:
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError("GOOGLE_SPREADSHEET_ID no está definida")
    client = _get_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=sheet_name, rows=5000, cols=len(HEADERS))
        ws.append_row(HEADERS)
    return ws


def _get_existing_ids(ws: gspread.Worksheet) -> set[str]:
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return set()
    return {row[0] for row in all_values[1:] if row}


# ── Escritura inicial ──────────────────────────────────────────────────────────

def save_contacts_to_sheet(contacts: list[dict], sheet_name: str = "Contactos") -> int:
    """
    Guarda contactos nuevos en el sheet (deduplicación por ID).
    Retorna el número de filas nuevas escritas.
    """
    ws = _open_worksheet(sheet_name)
    existing_ids = _get_existing_ids(ws)
    new_rows = []

    for contact in contacts:
        if contact.get("id") in existing_ids:
            continue
        row = [str(contact.get(key, "")) for key in CONTACT_KEYS]
        # Email Enviado, Resend ID, Email Abierto, Email Entregado, Rebote
        row += ["No", "", "No", "No", "No"]
        new_rows.append(row)

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return len(new_rows)


# ── Lectura de pendientes ──────────────────────────────────────────────────────

def get_pending_email_rows(sheet_name: str = "Contactos") -> list[dict]:
    """
    Retorna filas donde 'Email Enviado' == 'No' y hay email válido.
    Incluye '_row_index' para poder actualizar después.
    """
    ws = _open_worksheet(sheet_name)
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return []

    headers = all_values[0]
    pending = []
    for i, row in enumerate(all_values[1:], start=2):
        row_dict = dict(zip(headers, row))
        if row_dict.get("Email Enviado", "").strip() in ("No", "") and row_dict.get("Email"):
            row_dict["_row_index"] = i
            pending.append(row_dict)

    return pending


# ── Actualizaciones post-envío ─────────────────────────────────────────────────

def mark_email_sent(row_index: int, resend_id: str, sheet_name: str = "Contactos") -> None:
    """
    Marca la fila como enviada y guarda el Resend ID para rastrear webhooks.
    """
    ws = _open_worksheet(sheet_name)
    col_sent = HEADERS.index("Email Enviado") + 1
    col_resend_id = HEADERS.index("Resend ID") + 1

    ws.batch_update([
        {
            "range": gspread.utils.rowcol_to_a1(row_index, col_sent),
            "values": [["Sí"]],
        },
        {
            "range": gspread.utils.rowcol_to_a1(row_index, col_resend_id),
            "values": [[resend_id]],
        },
    ])


# ── Actualización por webhook ──────────────────────────────────────────────────

def update_email_event(resend_id: str, event_type: str, sheet_name: str = "Contactos") -> bool:
    """
    Busca la fila cuyo 'Resend ID' coincida y actualiza la columna del evento.
    event_type: 'email.opened' | 'email.delivered' | 'email.bounced'
    Retorna True si encontró y actualizó la fila, False si no la encontró.
    """
    col_name = EVENT_COLUMN_MAP.get(event_type)
    if not col_name:
        print(f"[sheets] Evento desconocido ignorado: {event_type}")
        return False

    ws = _open_worksheet(sheet_name)
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return False

    headers = all_values[0]
    try:
        resend_id_col_idx = headers.index("Resend ID")
        event_col_idx = headers.index(col_name)
    except ValueError:
        print(f"[sheets] Columna no encontrada: 'Resend ID' o '{col_name}'")
        return False

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > resend_id_col_idx and row[resend_id_col_idx] == resend_id:
            # Evitar escritura redundante si ya estaba marcado (email.opened dispara múltiples veces)
            current_value = row[event_col_idx] if len(row) > event_col_idx else ""
            if current_value == "Sí":
                print(f"[sheets] Fila {i} ya estaba marcada — {col_name} = Sí (skip)")
                return True
            cell = gspread.utils.rowcol_to_a1(i, event_col_idx + 1)
            ws.update(cell, "Sí")
            print(f"[sheets] Fila {i} actualizada — {col_name} = Sí (Resend ID: {resend_id})")
            return True

    print(f"[sheets] No se encontró fila con Resend ID: {resend_id}")
    return False


# ── Scraper leads ──────────────────────────────────────────────────────────────

def _get_existing_phones(ws: gspread.Worksheet) -> set[str]:
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return set()
    try:
        phone_col = all_values[0].index("Teléfono")
    except ValueError:
        return set()
    return {row[phone_col] for row in all_values[1:] if len(row) > phone_col and row[phone_col]}


def save_scraper_leads_to_sheet(leads: list[dict], sheet_name: str = "Contactos") -> int:
    """
    Guarda leads del scraper de Google Maps en el sheet.
    Deduplicación por teléfono.

    Cada lead debe tener: nombre, telefono, email, website
    """
    ws = _open_worksheet(sheet_name)
    existing_phones = _get_existing_phones(ws)
    new_rows = []

    from datetime import date
    today = date.today().isoformat()

    for lead in leads:
        phone = lead.get("telefono", "").strip()
        if not phone or phone in existing_phones:
            continue

        row = [
            f"scraper-{phone}",       # ID
            lead.get("nombre", ""),   # Nombre
            lead.get("email", ""),    # Email
            phone,                    # Teléfono
            "",                       # Teléfono Móvil
            lead.get("nombre", ""),   # Empresa
            "Google Maps",            # Fuente
            "",                       # Etapa
            "",                       # Estatus
            today,                    # Creado en
            today,                    # Actualizado en
            "No",                     # Email Enviado
            "",                       # Resend ID
            "No",                     # Email Abierto
            "No",                     # Email Entregado
            "No",                     # Rebote
            lead.get("website", ""),  # Web
        ]
        new_rows.append(row)
        existing_phones.add(phone)

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return len(new_rows)


def get_rows_needing_email_enrichment(sheet_name: str = "Contactos") -> list[dict]:
    """Filas donde Email está vacío pero Web tiene URL."""
    ws = _open_worksheet(sheet_name)
    all_values = ws.get_all_values()
    if len(all_values) <= 1:
        return []

    headers = all_values[0]
    pending = []
    for i, row in enumerate(all_values[1:], start=2):
        row_dict = dict(zip(headers, row))
        if not row_dict.get("Email", "").strip() and row_dict.get("Web", "").strip():
            row_dict["_row_index"] = i
            pending.append(row_dict)

    return pending


def update_email_for_row(row_index: int, email: str, sheet_name: str = "Contactos") -> None:
    """Escribe el email encontrado en la fila correspondiente."""
    ws = _open_worksheet(sheet_name)
    col_email = HEADERS.index("Email") + 1
    cell = gspread.utils.rowcol_to_a1(row_index, col_email)
    ws.update(cell, email)
