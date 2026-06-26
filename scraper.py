"""
Google Maps scraper para inmobiliarias en México.
Guarda directo a Google Sheets (mismo sheet del sistema de outreach).

Uso:
    python scraper.py --city CDMX              # scrape una ciudad completa
    python scraper.py --city QUERETARO
    python scraper.py --list-cities            # ver ciudades disponibles
    python scraper.py --city CDMX --max-results 150   # limita por query
    python scraper.py --city CDMX --csv backup.csv    # también guarda CSV
    python scraper.py --city CDMX --no-sheets         # solo CSV
    python scraper.py --city CDMX --headless false    # browser visible (debug)

Variables de entorno requeridas para Sheets:
    GOOGLE_SPREADSHEET_ID
    GOOGLE_SERVICE_ACCOUNT_JSON
"""

import argparse
import asyncio
import csv
import re
from contextlib import suppress
from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import Locator, Page, async_playwright

from cities import get_queries, list_cities
from outreach_system.config import get_settings

load_dotenv()


@dataclass
class Business:
    nombre: str = ""
    telefono: str = ""
    ciudad: str = ""
    direccion: str = ""
    website: str = ""
    rating: str = ""
    reviews: str = ""
    categoria: str = ""
    email: str = ""


# ── Extracción de un negocio ───────────────────────────────────────────────────

async def extract_business(page: Page) -> Business:
    biz = Business()

    with suppress(Exception):
        biz.nombre = await page.locator("h1.DUwDvf").first.inner_text(timeout=3000)

    with suppress(Exception):
        biz.categoria = await page.locator("button.DkEaL").first.inner_text(timeout=2000)

    try:
        address_el = page.locator('[data-item-id="address"]')
        if await address_el.count() > 0:
            raw = await address_el.first.get_attribute("aria-label", timeout=2000) or ""
            biz.direccion = raw.replace("Dirección: ", "").replace("Address: ", "").strip()
            parts = [p.strip() for p in biz.direccion.split(",")]
            if len(parts) >= 2:
                biz.ciudad = parts[-2]
    except Exception:
        pass

    try:
        phone_el = page.locator('[data-item-id^="phone:tel:"]')
        if await phone_el.count() > 0:
            label = await phone_el.first.get_attribute("aria-label", timeout=2000) or ""
            biz.telefono = re.sub(
                r"[^\d+\s\-()]", "",
                label.replace("Teléfono:", "").replace("Phone:", "")
            ).strip()
    except Exception:
        pass

    try:
        web_el = page.locator('[data-item-id="authority"]')
        if await web_el.count() > 0:
            biz.website = await web_el.first.get_attribute("href", timeout=2000) or ""
    except Exception:
        pass

    with suppress(Exception):
        biz.rating = await page.locator(
            "div.F7nice span[aria-hidden='true']"
        ).first.inner_text(timeout=2000)

    try:
        reviews_raw = await page.locator(
            "div.F7nice span[aria-label]"
        ).first.get_attribute("aria-label", timeout=2000) or ""
        biz.reviews = re.sub(r"[^\d,]", "", reviews_raw)
    except Exception:
        pass

    return biz


# ── Scroll ────────────────────────────────────────────────────────────────────

async def slow_scroll(page: Page, container_selector: str, times: int = 3):
    for _ in range(times):
        await page.eval_on_selector(container_selector, "el => el.scrollBy(0, 800)")
        await asyncio.sleep(1.2)


# ── Scraper principal ─────────────────────────────────────────────────────────

async def scrape_google_maps(
    queries: list[str],
    max_results: int = 100,
    headless: bool = True,
) -> list[Business]:
    all_results: list[Business] = []
    seen_hrefs: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            locale="es-MX",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        context.set_default_timeout(60000)
        page = await context.new_page()

        for query in queries:
            print(f"\n[*] Buscando: {query}")
            encoded = query.replace(" ", "+")
            await page.goto(
                f"https://www.google.com/maps/search/{encoded}",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await asyncio.sleep(4)

            try:
                accept_btn = page.locator('button[aria-label*="Aceptar"]').first
                if await accept_btn.count() > 0:
                    await accept_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            results_selector = 'div[role="feed"]'
            try:
                await page.wait_for_selector(results_selector, timeout=10000)
            except Exception:
                print(f"  [!] No se encontró lista de resultados para: {query}")
                continue

            collected = 0
            no_new_count = 0

            while collected < max_results and no_new_count < 5:
                listings: list[Locator] = await page.locator('a[href*="/maps/place/"]').all()

                new_found = False
                for listing in listings:
                    if collected >= max_results:
                        break

                    href = await listing.get_attribute("href") or ""
                    if href in seen_hrefs:
                        continue

                    seen_hrefs.add(href)
                    new_found = True

                    try:
                        await listing.click()
                        await asyncio.sleep(2.5)

                        biz = await extract_business(page)
                        if biz.nombre and biz.nombre not in {b.nombre for b in all_results}:
                            biz.categoria = biz.categoria or query
                            all_results.append(biz)
                            collected += 1
                            print(
                                f"  [{collected:>3}] {biz.nombre} | "
                                f"{biz.telefono or 'sin tel'} | "
                                f"{biz.ciudad or 'sin ciudad'} | "
                                f"{'✓ web' if biz.website else '—'}"
                            )

                        await page.go_back()
                        await asyncio.sleep(1.5)

                    except Exception as e:
                        print(f"  [!] Error: {e}")
                        try:
                            await page.go_back()
                            await asyncio.sleep(1)
                        except Exception:
                            pass

                no_new_count = 0 if new_found else no_new_count + 1

                with suppress(Exception):
                    await slow_scroll(page, results_selector, times=3)

                try:
                    end_msg = await page.locator(
                        'span:has-text("Llegaste al final de la lista")'
                    ).count()
                    if end_msg > 0:
                        print("  [*] Fin de la lista.")
                        break
                except Exception:
                    pass

            await asyncio.sleep(4)

        await browser.close()

    return all_results


# ── Guardar ───────────────────────────────────────────────────────────────────

def save_to_csv(businesses: list[Business], output_file: str):
    path = Path(output_file)
    field_names = [f.name for f in fields(Business)]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for biz in businesses:
            writer.writerow({f.name: getattr(biz, f.name) for f in fields(Business)})
    print(f"CSV guardado: {output_file}")


def save_to_sheets(businesses: list[Business]) -> int:
    from sheets_client import save_scraper_leads_to_sheet
    leads = [
        {
            "nombre":  b.nombre,
            "telefono": re.sub(r"[^\d+]", "", b.telefono),
            "email":   b.email,
            "website": b.website,
        }
        for b in businesses
        if b.telefono
    ]
    written = save_scraper_leads_to_sheet(leads)
    print(f"Google Sheets: {written} filas nuevas escritas")
    return written


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(
    city: str,
    max_results: int,
    csv_path: str | None,
    skip_sheets: bool,
    headless: bool,
):
    queries = get_queries(city)
    print(f"\nCiudad: {city} — {len(queries)} zonas a scrapear")
    results = await scrape_google_maps(queries, max_results=max_results, headless=headless)

    if not results:
        print("[!] No se encontraron resultados.")
        return

    # Deduplicar localmente por teléfono
    seen_phones: set[str] = set()
    unique: list[Business] = []
    for b in results:
        phone_clean = re.sub(r"[^\d+]", "", b.telefono)
        if phone_clean and phone_clean not in seen_phones:
            seen_phones.add(phone_clean)
            unique.append(b)

    print(f"\nTotal únicos: {len(unique)}")
    print(f"Con sitio web: {sum(1 for b in unique if b.website)}")

    if csv_path:
        save_to_csv(unique, csv_path)

    if not skip_sheets:
        settings = get_settings()
        has_config = bool(
            settings.google_spreadsheet_id and settings.google_service_account_json
        )
        if has_config:
            save_to_sheets(unique)
        else:
            print("[!] Variables de Sheets no configuradas — omitiendo escritura al sheet")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Maps scraper — inmobiliarias MX")
    parser.add_argument("--city", required=False, default=None,
                        help="Ciudad a scrapear (ej: CDMX, QUERETARO, GUADALAJARA)")
    parser.add_argument("--list-cities", action="store_true",
                        help="Muestra ciudades disponibles y cuántas zonas tiene cada una")
    parser.add_argument("--max-results", type=int, default=150,
                        help="Máximo de resultados por zona/query (default: 150)")
    parser.add_argument("--csv", default=None, metavar="ARCHIVO",
                        help="Guardar también CSV de backup")
    parser.add_argument("--no-sheets", action="store_true",
                        help="No escribir al Google Sheet")
    parser.add_argument("--headless", default="true",
                        help="'false' para ver el browser (debug)")
    args = parser.parse_args()

    if args.list_cities:
        list_cities()
    elif not args.city:
        parser.error("Se requiere --city o --list-cities")
    else:
        asyncio.run(main(
            city=args.city,
            max_results=args.max_results,
            csv_path=args.csv,
            skip_sheets=args.no_sheets,
            headless=args.headless.lower() != "false",
        ))
