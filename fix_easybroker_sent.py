"""
Script de un solo uso: marca todas las filas de EasyBroker como 'Email Enviado = Sí'.
Corre una vez y elimina el archivo.

  python fix_easybroker_sent.py --dry-run   # ver cuántas filas afecta
  python fix_easybroker_sent.py             # aplicar cambio
"""

import argparse

import gspread
from dotenv import load_dotenv

from sheets_client import _open_worksheet

load_dotenv()


def main(dry_run: bool) -> None:
    ws = _open_worksheet("Contactos")
    all_values = ws.get_all_values()

    if len(all_values) <= 1:
        print("Sheet vacío.")
        return

    headers = all_values[0]
    try:
        fuente_col = headers.index("Fuente")
        sent_col = headers.index("Email Enviado")
    except ValueError as e:
        print(f"Columna no encontrada: {e}")
        return

    updates = []
    count = 0
    for i, row in enumerate(all_values[1:], start=2):
        fuente = row[fuente_col] if len(row) > fuente_col else ""
        sent = row[sent_col] if len(row) > sent_col else ""
        if fuente == "EasyBroker" and sent != "Sí":
            count += 1
            cell = gspread.utils.rowcol_to_a1(i, sent_col + 1)
            updates.append({"range": cell, "values": [["Sí"]]})

    print(f"Filas EasyBroker pendientes encontradas: {count}")

    if dry_run:
        print("Dry-run: no se escribió nada.")
        return

    if updates:
        ws.batch_update(updates)
        print(f"Listo: {count} filas marcadas como 'Email Enviado = Sí'.")
    else:
        print("Nada que actualizar.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
