"""
Realtek Outreach System
========================
Diseñado para correr como GitHub Actions cron job (--run-now).
El webhook server es un proceso separado (webhook_server.py).

Uso local:
  python main.py --run-now              # una corrida completa
  python main.py --run-now --max-emails 20  # limitar emails por corrida

GitHub Actions llama siempre con --run-now --max-emails N.
"""

import argparse
import os

from dotenv import load_dotenv

from easybroker_client import get_parsed_contacts
from sheets_client import (
    get_pending_email_rows,
    mark_email_sent,
    save_contacts_to_sheet,
)
from email_client import send_all_with_delay

load_dotenv()


def _on_email_sent(row: dict, resend_id: str, from_email: str) -> None:
    """Persiste el Resend ID en el sheet inmediatamente después de cada envío."""
    row_index = row.get("_row_index")
    if row_index:
        try:
            mark_email_sent(row_index, resend_id)
            print(f"[pipeline] Fila {row_index} marcada — desde: {from_email}")
        except Exception as exc:
            print(f"[pipeline] No se pudo marcar fila {row_index}: {exc}")


def run_pipeline(max_emails: int = 0, days_back: int = 0) -> None:
    print("\n========================================")
    print("  Realtek Outreach Pipeline — INICIO")
    if max_emails:
        print(f"  Límite de emails esta corrida: {max_emails}")
    if days_back:
        print(f"  Retrocediendo {days_back} día(s) en el filtro de EasyBroker")
    print("========================================\n")

    # ── 1. Fetch contactos de EasyBroker ──────────────────────────────────────
    print("[1/4] Extrayendo contactos de EasyBroker...")
    try:
        contacts = get_parsed_contacts(days_back=days_back)
        print(f"      {len(contacts)} contactos obtenidos.")
    except Exception as exc:
        print(f"[ERROR] EasyBroker: {exc}")
        raise SystemExit(1)

    if not contacts:
        print("      Sin contactos. Finalizando.")
        return

    # ── 2. Guardar en Google Sheets ────────────────────────────────────────────
    print("[2/4] Guardando en Google Sheets...")
    try:
        new_rows = save_contacts_to_sheet(contacts)
        print(f"      {new_rows} filas nuevas escritas.")
    except Exception as exc:
        print(f"[ERROR] Google Sheets (escritura): {exc}")
        raise SystemExit(1)

    # ── 3. Leer pendientes ─────────────────────────────────────────────────────
    print("[3/4] Leyendo filas con 'Email Enviado = No'...")
    try:
        pending = get_pending_email_rows()
        print(f"      {len(pending)} correos pendientes en total.")
    except Exception as exc:
        print(f"[ERROR] Google Sheets (lectura): {exc}")
        raise SystemExit(1)

    if not pending:
        print("      Sin correos pendientes. Finalizando.\n")
        return

    # Aplicar límite por corrida (para controlar minutos de GitHub Actions)
    if max_emails and max_emails < len(pending):
        print(f"      Procesando {max_emails} de {len(pending)} pendientes esta corrida.")
        pending = pending[:max_emails]

    # ── 4. Envío con delay y rotación de remitentes ────────────────────────────
    d_min = int(os.getenv("SEND_DELAY_MIN_SECONDS", "120"))
    d_max = int(os.getenv("SEND_DELAY_MAX_SECONDS", "180"))
    print(f"[4/4] Enviando {len(pending)} emails (1 cada {d_min//60}–{d_max//60} min)...\n")

    sent, failed = send_all_with_delay(pending, on_sent_callback=_on_email_sent)

    print(f"\n      Enviados: {sent} | Fallidos: {failed}")
    print("\n========================================")
    print("  Pipeline completado.")
    print("========================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Realtek Outreach Pipeline")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Ejecuta el pipeline (requerido; GitHub Actions siempre lo pasa)",
    )
    parser.add_argument(
        "--max-emails",
        type=int,
        default=0,
        metavar="N",
        help="Máximo de emails a enviar en esta corrida (0 = sin límite)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=0,
        metavar="N",
        help="Días hacia atrás en el filtro de EasyBroker (0 = hoy, 1 = ayer, etc.)",
    )
    args = parser.parse_args()

    run_pipeline(max_emails=args.max_emails, days_back=args.days_back)


if __name__ == "__main__":
    main()
