import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Generator

EASYBROKER_API_URL = "https://api.easybroker.com/v1"
PAGE_LIMIT = 50
MEXICO_TZ = ZoneInfo("America/Mexico_City")


def _get_headers() -> dict:
    api_key = (os.getenv("EASYBROKER_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("EASYBROKER_API_KEY no está definida en las variables de entorno")
    return {
        "accept": "application/json",
        "X-Authorization": api_key,
    }


def _updated_after_filter(days_back: int = 0) -> str:
    """
    Retorna las 00:00 del día objetivo en hora México.
    days_back=0 → hoy a las 00:00 (comportamiento normal).
    days_back=1 → ayer a las 00:00 (útil cuando el outreach fue después del job).

    Ejemplo: job corre hoy 16 abr, days_back=1 → "2026-04-15T00:00:00-06:00"
    """
    from datetime import timedelta
    now_mx = datetime.now(MEXICO_TZ)
    target_day = now_mx - timedelta(days=days_back)
    start_of_day = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day.isoformat()


def fetch_contacts_paginated(days_back: int = 0) -> Generator[list[dict], None, None]:
    """
    Genera páginas de contactos desde EasyBroker.
    days_back=0 → filtra desde hoy 00:00 (default).
    days_back=1 → filtra desde ayer 00:00.
    """
    updated_after = _updated_after_filter(days_back)
    print(f"[easybroker] Filtrando contactos actualizados después de: {updated_after}")

    params = {
        "page": 1,
        "limit": PAGE_LIMIT,
        "search[updated_after]": updated_after,
    }
    headers = _get_headers()

    while True:
        response = requests.get(
            f"{EASYBROKER_API_URL}/contacts",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        contacts = data.get("content", [])
        if not contacts:
            break

        yield contacts

        pagination = data.get("pagination", {})
        if not pagination.get("next_page"):
            break

        params["page"] += 1


def fetch_all_contacts(days_back: int = 0) -> list[dict]:
    """Retorna todos los contactos del período concatenando todas las páginas."""
    all_contacts = []
    for page in fetch_contacts_paginated(days_back):
        all_contacts.extend(page)
    return all_contacts


def parse_contact(raw: dict) -> dict:
    return {
        "id": str(raw.get("id", "")),
        "name": raw.get("name", ""),
        "email": raw.get("email", ""),
        "phone": raw.get("phone", ""),
        "mobile_phone": raw.get("mobile_phone", ""),
        "company": raw.get("company", ""),
        "source": raw.get("source", ""),
        "stage": raw.get("stage", ""),
        "status": raw.get("status", ""),
        "created_at": raw.get("created_at", ""),
        "updated_at": raw.get("updated_at", ""),
    }


def get_parsed_contacts(days_back: int = 0) -> list[dict]:
    """Pipeline completo: fetch + parse de contactos del período."""
    raw_contacts = fetch_all_contacts(days_back)
    return [parse_contact(c) for c in raw_contacts]
