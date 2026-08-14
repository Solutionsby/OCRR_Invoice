import platform
from pathlib import Path

from pdf2image import convert_from_path
import pytesseract

from config import config_manager as cfg
from utils import knowledge_manager as km
from utils import file_manager
from utils import database_manager as db
from file_renamer import rename_file
from extracters.extract_firm_name import extract_firm_name
from extracters.extract_invoice_number import extract_invoice_number
from extracters.extract_invoice_date import extract_invoice_date
from extracters.extract_payment_date import extract_payment_date
from extracters.extract_payment_info import (
    extract_payment_status, extract_payment_form, is_paid,
    status_is_missing, assume_unpaid_via_transfer_heuristic, assume_paid_via_cod_heuristic,
)
from extracters.extract_gross_amount import extract_gross_amount
from core.paths import dest_dir, payment_dir, manual_dir

if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def analyze_ksef(pdf_path: Path) -> dict:
    """
    Czysta ekstrakcja OCR + odczyt pól dla faktury KSeF — bez żadnych promptów
    (w przeciwieństwie do dawnego main.py, które w tym miejscu potrafiło
    zablokować się na input()). Gdy KSeF nie podał "Informacja o płatności" i
    nie da się tego jednoznacznie wywnioskować z formy płatności / porównania
    dat, zwracamy payment_status_ambiguous=True zamiast pytać od razu —
    operator (CLI albo przeglądarka) rozstrzyga to razem z resztą pól.
    """
    path_to_poppler = r'C:\poppler\Library\bin' if platform.system() == 'Windows' else None
    images = convert_from_path(str(pdf_path), poppler_path=path_to_poppler)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, lang='pol') + "\n"

    # Odczyt lewej połowy pierwszej strony osobno — część wizualizacji KSeF
    # (np. wFirma.pl) ma układ dwukolumnowy Sprzedawca/Nabywca, przez co
    # Tesseract potrafi pomieszać obie kolumny przy odczycie całej strony.
    left_column_text = ""
    if images:
        width, height = images[0].size
        left_half = images[0].crop((0, 0, width // 2, height))
        left_column_text = pytesseract.image_to_string(left_half, lang='pol')

    patterns = cfg.load_patterns()
    scanned_firm = extract_firm_name(text, left_column_text=left_column_text).strip()
    proposed_firm = cfg.get_firm_data(scanned_firm, patterns)

    date = extract_invoice_date(text)
    pay_date = extract_payment_date(text)
    num = extract_invoice_number(text, proposed_firm)
    payment_status = extract_payment_status(text)
    payment_form = extract_payment_form(text)
    brutto = extract_gross_amount(text)

    payment_status_ambiguous = False
    if status_is_missing(payment_status):
        if assume_paid_via_cod_heuristic(payment_form):
            payment_status = "Zapłacono (pobranie)"
        elif assume_unpaid_via_transfer_heuristic(payment_form, date, pay_date):
            payment_status = "Brak zapłaty (przelew, termin po dacie wystawienia)"
        else:
            payment_status_ambiguous = True

    return {
        "file_name": pdf_path.name,
        "scanned_firm": scanned_firm,
        "firm_name": proposed_firm,
        "invoice_number": num,
        "invoice_date": date,
        "payment_date": pay_date,
        "payment_status": payment_status,
        "payment_status_ambiguous": payment_status_ambiguous,
        "payment_form": payment_form,
        "brutto": brutto,
        "kategoria": "",
        "duplicate_matches": db.find_duplicates(num),
    }


def finalize_ksef(pdf_path: Path, data: dict, action: str) -> dict:
    """
    Wykonuje to, co dawny main.py robił po potwierdzeniu operatora: zmianę
    nazwy, segregację do folderu, zapis do bazy płatności i naukę aliasów
    firmy. `action` to ten sam tryb co dawne `confirm` w main.py: 't'/inne
    (akceptacja), 'n'/'nie' (po korekcie), 'k' (kolejkuj do wpisania
    ręcznego — tryb błyskawiczny, bez nauki bazy wiedzy, tak jak dawniej).
    """
    if action != 'k':
        km.update_firm_knowledge(data["firm_name"], data.get("kategoria", ""))
        cfg.update_knowledge_base(data["scanned_firm"], data["firm_name"])

    result = rename_file(
        pdf_path, "",
        manual_num=data["invoice_number"],
        manual_firm=data["firm_name"],
        manual_date=data["invoice_date"],
    )
    new_pdf_name = result["new_path"].name

    final_data = {
        "invoice_number": data["invoice_number"],
        "firm_name": data["firm_name"],
        "invoice_date": data["invoice_date"],
        "payment_date": data["payment_date"],
        "payment_status": data["payment_status"],
        "payment_form": data["payment_form"],
        "oplacona": is_paid(data["payment_status"]),
        "brutto": data["brutto"],
        "kategoria": data.get("kategoria", ""),
        "file_name": new_pdf_name,
    }

    target_full_path = file_manager.get_target_path(
        dest_dir(), payment_dir(), manual_dir(), final_data, action
    )
    file_manager.move_file(result["new_path"], target_full_path)

    saved_to_payments = False
    if file_manager.needs_payment(final_data):
        final_data["file_path"] = str(target_full_path)
        saved_to_payments = db.save_to_faktury_do_zaplaty(final_data)

    final_data["target_path"] = str(target_full_path)
    final_data["saved_to_payments"] = saved_to_payments
    return final_data
