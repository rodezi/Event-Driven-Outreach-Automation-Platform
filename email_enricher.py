"""
Email enricher — visita sitios web del sheet y busca emails en el HTML.
Lee filas donde Email está vacío y la columna 'Web' tiene URL.
Actualiza el email directo en el sheet.

Uso:
    python email_enricher.py                  # todas las filas pendientes
    python email_enricher.py --limit 200      # máximo 200 por corrida
    python email_enricher.py --dry-run        # simula sin escribir al sheet

Variables de entorno requeridas:
    GOOGLE_SPREADSHEET_ID
    GOOGLE_SERVICE_ACCOUNT_JSON
"""

import asyncio
import argparse
import re

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser

from sheets_client import get_rows_needing_email_enrichment, update_email_for_row

load_dotenv()

EMAIL_BLACKLIST = [
    "example", "sentry", "noreply", "no-reply", "wordpress", "wixpress",
    "squarespace", "schema.org", "w3.org", "yoursite", "yourdomain",
    "support@wix", "pixel", "cdn@", "privacy@", "legal@", "abuse@",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CONTACT_PATHS = ["/contacto", "/contact", "/nosotros", "/about", "/about-us", "/quienes-somos"]


def is_valid_email(email: str) -> bool:
    return not any(b in email.lower() for b in EMAIL_BLACKLIST)


def extract_emails_from_html(html: str) -> list[str]:
    found = EMAIL_RE.findall(html)
    return [e for e in found if is_valid_email(e)]


async def find_email_in_site(url: str, browser: Browser) -> str:
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
        page = None
        try:
            page = await browser.new_page()
            await page.goto(page_url, timeout=12000, wait_until="domcontentloaded")
            html = await page.content()
            await page.close()

            emails = extract_emails_from_html(html)
            if emails:
                return emails[0]
        except Exception:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            continue

    return ""


async def main(limit: int | None, dry_run: bool):
    print("Leyendo sheet...")
    rows = get_rows_needing_email_enrichment()

    if not rows:
        print("No hay filas pendientes de enriquecer.")
        return

    if limit:
        rows = rows[:limit]

    print(f"Filas a enriquecer: {len(rows)}")
    if dry_run:
        print("[DRY RUN] No se escribirá nada al sheet.\n")

    found = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        for i, row in enumerate(rows, start=1):
            nombre = row.get("Nombre", "")[:40]
            web = row.get("Web", "").strip()
            row_index = row["_row_index"]

            print(f"[{i:>3}/{len(rows)}] {nombre} → {web[:50]}", end=" ... ", flush=True)
            email = await find_email_in_site(web, browser)

            if email:
                found += 1
                print(email)
                if not dry_run:
                    update_email_for_row(row_index, email)
            else:
                print("—")

            await asyncio.sleep(1)

        await browser.close()

    print(f"\nEmails encontrados: {found}/{len(rows)}")
    if not dry_run:
        print("Sheet actualizado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enriquece emails desde sitios web")
    parser.add_argument("--limit", type=int, default=None,
                        help="Máximo de filas a procesar (default: todas)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sin escribir al sheet")
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, dry_run=args.dry_run))
