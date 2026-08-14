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
from utils import nbp_rate
from file_renamer import rename_file
from core.paths import DEST_DIR, PAYMENT_DIR, MANUAL_DIR

if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def analyze_euro(pdf_path: Path) -> dict:
    """
    Czysta ekstrakcja dla faktury EUR — bez promptów. Kwoty wracają w EUR,
    nieprzeliczone (konwersja zależy od kursu, który operator dopiero
    potwierdzi — patrz finalize_euro). suggested_rate/rate_date to
    podpowiedź z NBP (kurs z dnia poprzedzającego datę wystawienia); None,
    gdy NBP nie odpowiedziało — wtedy operator musi wpisać kurs ręcznie,
    tak jak dawny main_euro.py wymuszał to przez ui.ask_exchange_rate.
    Dział/kategoria: jak w core/inne.py.
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

    suggested_rate, rate_date = nbp_rate.get_nbp_rate("eur", invoice_date)
    dzial, kategoria = dk.get_dzial_kategoria(firm_name)
    invoice_number = extract_invoice_number(text)

    return {
        "file_name": pdf_path.name,
        "firm_name": firm_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "payment_date": extract_due_date(text, invoice_date),
        "eur_netto": amounts["netto"],
        "eur_vat": amounts["vat"],
        "eur_brutto": amounts["brutto"],
        "source": amounts["source"],
        "suggested_rate": suggested_rate,
        "rate_date": rate_date,
        "dzial": dzial or "",
        "kategoria": kategoria or "",
        "dzial_known": dzial is not None,
        "duplicate_matches": db.find_duplicates(invoice_number),
    }


def finalize_euro(pdf_path: Path, data: dict, action: str) -> dict:
    """
    action: 't' (akceptacja) | 'n' (po korekcie) — tak jak w core/inne.py, bez
    trybu 'k'. `data` musi zawierać netto/vat już przeliczone na PLN (przez
    kurs potwierdzony przez operatora) oraz eur_netto/eur_vat/kurs_eur
    (oryginalne kwoty EUR i użyty kurs) — te dwa ostatnie trafiają do pola
    "opis" w FAKTURY_KOSZTOWE jako ślad przeliczenia, tak jak w dawnym
    main_euro.py. Brutto (PLN) zawsze przeliczane jako netto+vat, nigdy
    przyjmowane wprost.
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
    # Opis w FAKTURY_KOSZTOWE to varchar(50) — zwięzły ślad przeliczenia.
    opis = f"EUR {data['eur_netto']}/{data['eur_vat']} kurs {data['kurs_eur']}"[:50]

    final_data = {
        **data,
        "file_name": new_pdf_name,
        "brutto": brutto,
        "opis": opis,
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
