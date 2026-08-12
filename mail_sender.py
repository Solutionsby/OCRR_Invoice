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
import main as app

load_dotenv()

MONTH_PREFIX_RE = re.compile(r"^(\d{2})_(\d{4})_")

def _archive_paid_invoice(pdf_path: Path, firm_name: str) -> Path:
    """
    Przenosi wysłaną fakturę do archiwum Miesiąc/Firma — ten sam układ folderów,
    którego używa main.py dla opłaconych faktur. Miesiąc bierzemy z nazwy pliku
    (nadanej przez file_renamer.py jako "MM_YYYY_FV_..."), więc nie trzeba
    trzymać osobno daty wystawienia w bazie płatności.
    """
    match = MONTH_PREFIX_RE.match(pdf_path.name)
    month_num = match.group(1) if match else "00_Nieznany"

    target_folder = app.DEST_DIR / month_num / firm_name
    target_folder.mkdir(parents=True, exist_ok=True)
    target_path = target_folder / pdf_path.name

    if target_path.exists():
        target_path.unlink()
    shutil.move(str(pdf_path), target_path)
    return target_path

def send_payment_report(ignore_date_window: bool = False):
    # 1. Pobranie danych z bazy
    upcoming_payments, total_sum = pm.load_upcoming_payments_from_sql(ignore_date_window=ignore_date_window)


    if not upcoming_payments:
        print("\nℹ️ Brak faktur do zapłaty.")
        return

    # 2. Pobranie konfiguracji
    settings = cfg.load_settings()
    conf = settings.get("email_config")
    
    # --- TUTAJ JEST ZMIANA: POBIERANIE Z .env ---
    # Pobieramy string z .env i rozbijamy go po przecinku na listę
    raw_recipients = os.getenv("EMAIL_RECIPIENTS", "")
    recipient_list = [r.strip() for r in raw_recipients.split(",") if r.strip()]
    
    # Tworzymy jeden ciąg do nagłówka maila "To:"
    recipient_str = ", ".join(recipient_list)
    # --------------------------------------------

    if not recipient_list:
        print("❌ BŁĄD: Brak zdefiniowanych odbiorców w .env (EMAIL_RECIPIENTS)!")
        return
    sender_name = "Faktury Do Zapłaty"
    sender_email = os.getenv('SENDER')
    msg = EmailMessage()
    msg['Subject'] = f"Zbiorczy Raport Płatności - {datetime.now().strftime('%d.%m.%Y')}"
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = recipient_str
    
    # --- PRZYGOTOWANIE TREŚCI HTML (Pełna szerokość) ---
    today_str = datetime.now().strftime('%d.%m.%Y %H:%M')
    
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
    
    for p in upcoming_payments:
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

    # Ustawiamy treść HTML
    msg.add_alternative(html_body, subtype='html')

    # --- ZAŁĄCZNIKI ---
    # NazwaPliku w bazie to teraz pełna ścieżka do pliku (zapisywana przez
    # main.py w momencie przenoszenia faktury do folderu "do_zaplaty"),
    # więc bierzemy ją bezpośrednio, bez przeszukiwania folderów.
    added_ids = []
    attached_items = []  # (pdf_path, firm_name) — do przeniesienia po udanej wysyłce

    for p in upcoming_payments:
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
            else:
                print(f"⚠️ Plik nie istnieje pod zapisaną ścieżką: {pdf_path}")
        added_ids.append(p['id'])

    # --- WYSYŁKA ---
    try:
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(conf.get('smtp_port', 587))
        
        print(f"⏳ Wysyłanie raportu HTML do {conf.get('recipient')}...")
        
        if smtp_port == 465:
            server_conn = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=60)
        else:
            server_conn = smtplib.SMTP(smtp_server, smtp_port, timeout=60)
            server_conn.starttls()

        with server_conn as server:
            server.login(os.getenv('SENDER'), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
            
        print(f"✅ SUKCES: Raport HTML wysłany!")

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

if __name__ == "__main__":
    import sys
    # --all: pomija okno +/-7 dni i wysyła WSZYSTKIE nieopłacone faktury
    # z FAKTURY_DO_ZAPLATY, niezależnie od terminu płatności.
    force_all = "--all" in sys.argv
    send_payment_report(ignore_date_window=force_all)