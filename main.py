"""
Realtek Email Pipeline
======================
Lee contactos pendientes del Google Sheet y envía hasta 100 emails por corrida.
Corre automáticamente a las 7 AM CST via GitHub Actions.

Uso local:
  python main.py                    # envía hasta 100 emails
  python main.py --max-emails 20    # limitar para pruebas
"""

import argparse
import os

from dotenv import load_dotenv

from sheets_client import get_pending_email_rows, mark_email_sent
from email_client import send_all_with_delay

load_dotenv()


def _on_email_sent(row: dict, resend_id: str, from_email: str) -> None:
    row_index = row.get("_row_index")
    if row_index:
        try:
            mark_email_sent(row_index, resend_id)
            print(f"[pipeline] Fila {row_index} marcada — desde: {from_email}")
        except Exception as exc:
            print(f"[pipeline] No se pudo marcar fila {row_index}: {exc}")


def run_pipeline(max_emails: int = 100) -> None:
    print("\n========================================")
    print("  Realtek Email Pipeline — INICIO")
    print(f"  Límite esta corrida: {max_emails} emails")
    print("========================================\n")

    # ── 1. Leer pendientes del sheet ───────────────────────────────────────────
    print("[1/2] Leyendo contactos pendientes del sheet...")
    try:
        pending = get_pending_email_rows()
        print(f"      {len(pending)} pendientes en total.")
    except Exception as exc:
        print(f"[ERROR] Google Sheets: {exc}")
        raise SystemExit(1)

    if not pending:
        print("      Sin correos pendientes. Finalizando.\n")
        return

    if max_emails and max_emails < len(pending):
        print(f"      Enviando {max_emails} de {len(pending)} esta corrida.")
        pending = pending[:max_emails]

    # ── 2. Enviar con delay y rotación de remitentes ───────────────────────────
    d_min = int(os.getenv("SEND_DELAY_MIN_SECONDS", "120"))
    d_max = int(os.getenv("SEND_DELAY_MAX_SECONDS", "180"))
    print(f"[2/2] Enviando {len(pending)} emails (1 cada {d_min//60}–{d_max//60} min)...\n")

    sent, failed = send_all_with_delay(pending, on_sent_callback=_on_email_sent)

    print(f"\n      Enviados: {sent} | Fallidos: {failed}")
    print("\n========================================")
    print("  Pipeline completado.")
    print("========================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Realtek Email Pipeline")
    parser.add_argument("--max-emails", type=int, default=100,
                        help="Máximo de emails a enviar por corrida (default: 100)")
    args = parser.parse_args()
    run_pipeline(max_emails=args.max_emails)


if __name__ == "__main__":
    main()
