import platform
from pathlib import Path

from pdf2image import convert_from_path
import pytesseract

from extracters.inne.identity import extract_seller_name, is_single_page_invoice
from extracters.inne.numbers import extract_invoice_number
from extracters.inne.dates import extract_invoice_date, extract_due_date
from extracters.inne.amounts import extract_amounts
from utils import dzial_kategoria_manager as dk
from utils import file_manager
from utils import database_manager as db
from file_renamer import rename_file
from core.paths import DEST_DIR, PAYMENT_DIR, MANUAL_DIR

if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def analyze_inne(pdf_path: Path) -> dict:
    """
    Czysta ekstrakcja dla faktury spoza KSeF — bez promptów. W odróżnieniu od
    KSeF te faktury nie mają żadnej etykiety statusu płatności, więc pole
    "oplacona" nie jest tu w ogóle proponowane — operator musi je jawnie
    ustawić (tak jak dawny main_inne.py zawsze pytał wprost, bez domyślnej
    wartości). Dział/kategoria: jeśli kontrahent jest już znany w
    json/dzial_kategoria.json, zwracamy podpowiedź i dzial_known=True; jeśli
    nie, dzial_known=False i operator musi je wpisać.
    """
    path_to_poppler = r'C:\poppler\Library\bin' if platform.system() == 'Windows' else None
    images = convert_from_path(str(pdf_path), poppler_path=path_to_poppler)

    text = pytesseract.image_to_string(images[0], lang='pol') + "\n"
    if not is_single_page_invoice(text):
        for img in images[1:]:
            text += pytesseract.image_to_string(img, lang='pol') + "\n"

    invoice_date = extract_invoice_date(text)
    firm_name = extract_seller_name(text)
    amounts = extract_amounts(text)

    dzial, kategoria = dk.get_dzial_kategoria(firm_name)
    invoice_number = extract_invoice_number(text)

    return {
        "file_name": pdf_path.name,
        "firm_name": firm_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "payment_date": extract_due_date(text, invoice_date),
        "dzial": dzial or "",
        "kategoria": kategoria or "",
        "dzial_known": dzial is not None,
        "netto": amounts["netto"],
        "vat": amounts["vat"],
        "brutto": amounts["brutto"],
        "source": amounts["source"],
        "duplicate_matches": db.find_duplicates(invoice_number),
    }


def finalize_inne(pdf_path: Path, data: dict, action: str) -> dict:
    """
    action: 't' (akceptacja) | 'n' (po korekcie) — tryb 'k' (kolejkuj do
    wpisania ręcznego) nie istnieje w tym przepływie, tak jak w dawnym
    main_inne.py. Nauka dział/kategoria zapisywana zawsze — tak jak dawniej,
    gdy kontrahent był nieznany, i przy każdej korekcie operatora.

    Brutto nigdy nie jest przyjmowane wprost od operatora — zawsze
    przeliczane jako netto+vat, zgodnie z zasadą całego przepływu "inne"
    (patrz extracters/inne/amounts.py).
    """
    dk.update_dzial_kategoria(data["firm_name"], data["dzial"], data["kategoria"])

    result = rename_file(
        pdf_path, "",
        manual_num=data["invoice_number"],
        manual_firm=data["firm_name"],
        manual_date=data["invoice_date"],
    )
    new_pdf_name = result["new_path"].name

    brutto = round(data["netto"] + data["vat"], 2)
    final_data = {
        **data,
        "file_name": new_pdf_name,
        "brutto": brutto,
    }

    routing_data = {
        "firm_name": final_data["firm_name"],
        "invoice_date": final_data["invoice_date"],
        "payment_date": final_data["payment_date"],
        "oplacona": final_data["oplacona"],
        "file_name": new_pdf_name,
    }
    target_path = file_manager.get_target_path(DEST_DIR, PAYMENT_DIR, MANUAL_DIR, routing_data, action)
    file_manager.move_file(result["new_path"], target_path)

    saved_to_kosztowe = db.save_to_faktury_kosztowe(final_data)

    saved_to_payments = False
    if file_manager.needs_payment(routing_data):
        final_data["file_path"] = str(target_path)
        saved_to_payments = db.save_to_faktury_do_zaplaty(final_data)

    final_data["target_path"] = str(target_path)
    final_data["saved_to_kosztowe"] = saved_to_kosztowe
    final_data["saved_to_payments"] = saved_to_payments
    return final_data
