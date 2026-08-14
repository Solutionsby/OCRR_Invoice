import os
import re
import shutil
import smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from config import config_manager as cfg
import payment_manager as pm
from utils import database_manager as db
from core.paths import DEST_DIR

load_dotenv()

MONTH_PREFIX_RE = re.compile(r"^(\d{2})_(\d{4})_")


def get_recipients():
    """
    Odbiorcy pochodzą z settings.json (email_config.recipients) — edytowalne
    z przeglądarki bez restartu kontenera. .env zostaje tylko dla sekretów
    SMTP (SENDER/EMAIL_PASSWORD/SMTP_SERVER).
    """
    settings = cfg.load_settings()
    return settings.get("email_config", {}).get("recipients", [])


def _archive_paid_invoice(pdf_path: Path, firm_name: str) -> Path:
    """
    Przenosi wysłaną fakturę do archiwum Miesiąc/Firma — ten sam układ folderów,
    którego używa core/ksef.py (i core/inne.py, core/euro.py) dla opłaconych
    faktur. Miesiąc bierzemy z nazwy pliku (nadanej przez file_renamer.py jako
    "MM_YYYY_FV_..."), więc nie trzeba trzymać osobno daty wystawienia w bazie
    płatności.
    """
    match = MONTH_PREFIX_RE.match(pdf_path.name)
    month_num = match.group(1) if match else "00_Nieznany"

    target_folder = DEST_DIR / month_num / firm_name
    target_folder.mkdir(parents=True, exist_ok=True)
    target_path = target_folder / pdf_path.name

    if target_path.exists():
        target_path.unlink()
    shutil.move(str(pdf_path), target_path)
    return target_path


def _build_and_send(payments: list, recipients: list) -> dict:
    """
    Buduje jeden zbiorczy mail HTML dla podanych pozycji (z załącznikami PDF),
    wysyła, oznacza jako wysłane w SQL i archiwizuje załączone pliki.
    Współdzielone przez CLI (send_payment_report, cały czas wg okna dni) i API
    (send_by_ids, tylko ręcznie wybrane pozycje) — jedno miejsce z logiką
    wysyłki, żeby oba wywołania zachowywały się identycznie.
    """
    result = {"sent": False, "count": 0, "recipients": recipients, "missing_files": [], "error": None}

    if not payments:
        result["error"] = "Brak faktur do wysłania."
        return result
    if not recipients:
        result["error"] = "Brak zdefiniowanych odbiorców (settings.json: email_config.recipients)."
        return result

    settings = cfg.load_settings()
    conf = settings.get("email_config", {})
    recipient_str = ", ".join(recipients)

    sender_name = "Faktury Do Zapłaty"
    sender_email = os.getenv('SENDER')
    msg = EmailMessage()
    msg['Subject'] = f"Zbiorczy Raport Płatności - {datetime.now().strftime('%d.%m.%Y')}"
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = recipient_str

    today_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    total_sum = sum(p['brutto'] for p in payments)

    html_body = f"""
    <html>
    <head>
        <style>
            table {{
                width: 100%;
                border-collapse: collapse;
                font-family: Arial, sans-serif;
            }}
            th {{
                background-color: #f2f2f2;
                text-align: left;
                padding: 12px;
                border-bottom: 2px solid #ddd;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}
            .total {{
                font-weight: bold;
                background-color: #eee;
            }}
        </style>
    </head>
    <body>
        <h2>Raport faktur do opłacenia</h2>
        <p>Data wygenerowania raportu (wysyłki): <strong>{today_str}</strong></p>
        <table>
            <thead>
                <tr>
                    <th>Termin Płatności</th>
                    <th>Kontrahent</th>
                    <th>Numer Faktury</th>
                    <th style="text-align: right;">Kwota Brutto</th>
                </tr>
            </thead>
            <tbody>
    """

    for p in payments:
        html_body += f"""
                <tr>
                    <td>{p['payment_date']}</td>
                    <td>{p['firm_name']}</td>
                    <td>{p['invoice_number']}</td>
                    <td style="text-align: right;">{p['brutto']:.2f} zł</td>
                </tr>
        """

    html_body += f"""
                <tr class="total">
                    <td colspan="3" style="text-align: right;">RAZEM DO ZAPŁATY:</td>
                    <td style="text-align: right;">{total_sum:.2f} zł</td>
                </tr>
            </tbody>
        </table>
        <p><br>W załącznikach znajdziesz oryginalne pliki PDF.</p>
    </body>
    </html>
    """

    msg.add_alternative(html_body, subtype='html')

    # --- ZAŁĄCZNIKI ---
    # NazwaPliku w bazie to pełna ścieżka do pliku (zapisywana przy przenoszeniu
    # faktury do folderu "do_zaplaty"), więc bierzemy ją bezpośrednio, bez
    # przeszukiwania folderów.
    added_ids = []
    attached_items = []  # (pdf_path, firm_name) — do przeniesienia po udanej wysyłce

    for p in payments:
        file_path = p.get('file_name')
        if file_path:
            pdf_path = Path(file_path)
            if pdf_path.exists():
                try:
                    with open(pdf_path, 'rb') as f:
                        msg.add_attachment(
                            f.read(),
                            maintype='application',
                            subtype='pdf',
                            filename=pdf_path.name
                        )
                    attached_items.append((pdf_path, p['firm_name']))
                except Exception as e:
                    print(f"⚠️ Nie udało się dołączyć {pdf_path.name}: {e}")
                    result["missing_files"].append(str(pdf_path))
            else:
                print(f"⚠️ Plik nie istnieje pod zapisaną ścieżką: {pdf_path}")
                result["missing_files"].append(str(pdf_path))
        added_ids.append(p['id'])

    # --- WYSYŁKA ---
    try:
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(conf.get('smtp_port', 587))

        print(f"⏳ Wysyłanie raportu HTML do {recipient_str}...")

        if smtp_port == 465:
            server_conn = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=60)
        else:
            server_conn = smtplib.SMTP(smtp_server, smtp_port, timeout=60)
            server_conn.starttls()

        with server_conn as server:
            server.login(os.getenv('SENDER'), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)

        print(f"✅ SUKCES: Raport HTML wysłany!")
        result["sent"] = True
        result["count"] = len(payments)

        if added_ids:
            db.mark_as_sent(added_ids)

        # Wysłane faktury wędrują do archiwum Miesiąc/Firma, tak jak opłacone
        for pdf_path, firm_name in attached_items:
            try:
                target = _archive_paid_invoice(pdf_path, firm_name)
                print(f"📁 Przeniesiono do archiwum: {target}")
            except Exception as e:
                print(f"⚠️ Nie udało się przenieść {pdf_path.name} do archiwum: {e}")

    except Exception as e:
        print(f"❌ BŁĄD: {e}")
        result["error"] = str(e)

    return result


def send_payment_report(ignore_date_window: bool = False):
    """CLI/cron: wysyła wszystko, co pasuje do skonfigurowanego okna dni (albo
    wszystko nieopłacone/niewysłane, gdy ignore_date_window=True — flaga --all)."""
    days_window = cfg.load_settings().get("email_config", {}).get("days_window", 7)
    upcoming_payments, _ = pm.load_upcoming_payments_from_sql(
        days_window=days_window, ignore_date_window=ignore_date_window
    )
    if not upcoming_payments:
        print("\nℹ️ Brak faktur do zapłaty.")
        return
    _build_and_send(upcoming_payments, get_recipients())


def send_by_ids(ids: list) -> dict:
    """API: wysyła tylko ręcznie wskazane pozycje (operator odznaczył resztę
    w przeglądarce), niezależnie od okna dni."""
    payments = db.get_payments_by_ids(ids)
    return _build_and_send(payments, get_recipients())


if __name__ == "__main__":
    import sys
    # --all: pomija okno dni i wysyła WSZYSTKIE nieopłacone faktury
    # z FAKTURY_DO_ZAPLATY, niezależnie od terminu płatności.
    force_all = "--all" in sys.argv
    send_payment_report(ignore_date_window=force_all)
