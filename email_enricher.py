"""
Email enricher — visita sitios web del sheet y busca emails en el HTML.
Lee filas donde Email está vacío y la columna 'Web' tiene URL.
Usa requests + BeautifulSoup (sin browser, corre en GitHub Actions).

Uso:
    python email_enricher.py                  # todas las filas pendientes
    python email_enricher.py --limit 200      # máximo por corrida
    python email_enricher.py --dry-run        # simula sin escribir al sheet

Variables de entorno requeridas:
    GOOGLE_SPREADSHEET_ID
    GOOGLE_SERVICE_ACCOUNT_JSON
"""

import argparse
import re
import time

import requests
from dotenv import load_dotenv

from sheets_client import get_rows_needing_email_enrichment, update_email_for_row

load_dotenv()

EMAIL_BLACKLIST = [
    "example", "sentry", "noreply", "no-reply", "wordpress", "wixpress",
    "squarespace", "schema.org", "w3.org", "yoursite", "yourdomain",
    "support@wix", "pixel", "cdn@", "privacy@", "legal@", "abuse@",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CONTACT_PATHS = ["/contacto", "/contact", "/nosotros", "/about", "/about-us", "/quienes-somos"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9",
}


def is_valid_email(email: str) -> bool:
    return not any(b in email.lower() for b in EMAIL_BLACKLIST)


def extract_emails_from_html(html: str) -> list[str]:
    found = EMAIL_RE.findall(html)
    return [e for e in found if is_valid_email(e)]


def fetch_page(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


def find_email_in_site(url: str) -> str:
    """
    Busca email en el sitio:
    1. Página principal
    2. Si no encuentra, prueba rutas de contacto comunes
    """
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    base = url.rstrip("/")

    for page_url in [base] + [base + path for path in CONTACT_PATHS]:
        html = fetch_page(page_url)
        if not html:
            continue
        emails = extract_emails_from_html(html)
        if emails:
            return emails[0]

    return ""


def main(limit: int | None, dry_run: bool):
    print("Leyendo sheet...")
    rows, existing_emails = get_rows_needing_email_enrichment()

    if not rows:
        print("No hay filas pendientes de enriquecer.")
        return

    if limit:
        rows = rows[:limit]

    print(f"Filas a enriquecer: {len(rows)}")
    if dry_run:
        print("[DRY RUN] No se escribirá nada al sheet.\n")

    found = 0
    skipped_dup = 0
    for i, row in enumerate(rows, start=1):
        nombre = row.get("Nombre", "")[:40]
        web = row.get("Web", "").strip()
        row_index = row["_row_index"]

        print(f"[{i:>3}/{len(rows)}] {nombre} → {web[:50]}", end=" ... ", flush=True)
        email = find_email_in_site(web)

        if email:
            if email.lower() in existing_emails:
                skipped_dup += 1
                print(f"{email} [duplicado, omitido]")
            else:
                found += 1
                existing_emails.add(email.lower())
                print(email)
                if not dry_run:
                    update_email_for_row(row_index, email)
        else:
            print("—")

        time.sleep(1)

    print(f"\nEmails encontrados: {found}/{len(rows)}  |  Duplicados omitidos: {skipped_dup}")
    if not dry_run:
        print("Sheet actualizado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enriquece emails desde sitios web")
    parser.add_argument("--limit", type=int, default=None,
                        help="Máximo de filas a procesar (default: todas)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sin escribir al sheet")
    args = parser.parse_args()

    main(limit=args.limit, dry_run=args.dry_run)
