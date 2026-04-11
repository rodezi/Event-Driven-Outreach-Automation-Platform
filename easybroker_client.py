import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Generator

EASYBROKER_API_URL = "https://api.easybroker.com/v1"
PAGE_LIMIT = 50
MEXICO_TZ = ZoneInfo("America/Mexico_City")


def _get_headers() -> dict:
    api_key = os.getenv("EASYBROKER_API_KEY")
    if not api_key:
        raise ValueError("EASYBROKER_API_KEY no está definida en las variables de entorno")
    return {
        "accept": "application/json",
        "X-Authorization": api_key,
    }


def _updated_after_filter() -> str:
    """
    Retorna las 00:00 de hoy en hora México (inicio del día).
    Así se capturan todos los contactos creados/actualizados durante el día,
    sin importar a qué hora exacta se hizo el outreach manual.

    Ejemplo: job corre a las 19:00 del 10 abr → "2026-04-10T00:00:00-05:00"
    """
    now_mx = datetime.now(MEXICO_TZ)
    start_of_day = now_mx.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day.isoformat()


def fetch_contacts_paginated() -> Generator[list[dict], None, None]:
    """
    Genera páginas de contactos desde EasyBroker.
    Filtra con search[updated_after] = hoy a las 19:00 hora México.
    """
    updated_after = _updated_after_filter()
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


def fetch_all_contacts() -> list[dict]:
    """Retorna todos los contactos del día concatenando todas las páginas."""
    all_contacts = []
    for page in fetch_contacts_paginated():
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


def get_parsed_contacts() -> list[dict]:
    """Pipeline completo: fetch + parse de contactos del día."""
    raw_contacts = fetch_all_contacts()
    return [parse_contact(c) for c in raw_contacts]
