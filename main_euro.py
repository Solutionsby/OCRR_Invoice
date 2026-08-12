import platform
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

from extracters.inne.identity import extract_seller_name, is_single_page_invoice
from extracters.inne.numbers import extract_invoice_number
from extracters.inne.dates import extract_invoice_date, extract_due_date
from extracters.inne.amounts import extract_amounts
from utils import ui_handler as ui
from utils import dzial_kategoria_manager as dk
from utils import file_manager
from utils import database_manager as db
from utils import nbp_rate
from file_renamer import rename_file
from config import system_utils as sys_utils

if platform.system() == 'Windows':
    BASE_PATH = Path(r"Z:\Twoje_Faktury")
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    BASE_PATH = Path("./")

SOURCE_DIR = BASE_PATH / "faktury_surowe" / "euro"
# Ten sam docelowy drzewo i tabela FAKTURY_DO_ZAPLATY co dla faktur spoza
# KSeF — różnica jest tylko w przeliczeniu EUR->PLN przed zapisem.
DEST_DIR = BASE_PATH / "faktury_przetworzone"
PAYMENT_DIR = DEST_DIR / "do_zaplaty"
MANUAL_DIR = PAYMENT_DIR / "do_wpisania_recznie"


def read_invoice(pdf_path: Path) -> dict:
    path_to_poppler = r'C:\poppler\Library\bin' if platform.system() == 'Windows' else None
    images = convert_from_path(str(pdf_path), poppler_path=path_to_poppler)

    text = pytesseract.image_to_string(images[0], lang='pol') + "\n"
    if not is_single_page_invoice(text):
        for img in images[1:]:
            text += pytesseract.image_to_string(img, lang='pol') + "\n"

    invoice_date = extract_invoice_date(text)
    amounts = extract_amounts(text)

    return {
        "file_name": pdf_path.name,
        "firm_name": extract_seller_name(text),
        "invoice_number": extract_invoice_number(text),
        "invoice_date": invoice_date,
        "payment_date": extract_due_date(text, invoice_date),
        **amounts,
    }


def convert_to_pln(data: dict, rate: float):
    """
    Zamienia odczytane kwoty EUR na PLN. Oryginalne kwoty EUR i kurs
    zostają w 'opis' jako notatka do FAKTURY_KOSZTOWE (ślad przeliczenia),
    a netto/vat/brutto są od tej chwili traktowane jak w faktury_surowe/inne
    (brutto zawsze = netto+vat).
    """
    eur_netto, eur_vat = data["netto"], data["vat"]
    data["netto"] = round(eur_netto * rate, 2)
    data["vat"] = round(eur_vat * rate, 2)
    data["brutto"] = round(data["netto"] + data["vat"], 2)
    data["kurs_eur"] = rate
    # Opis w FAKTURY_KOSZTOWE to varchar(50) — zwięzły ślad przeliczenia.
    data["opis"] = f"EUR {eur_netto}/{eur_vat} kurs {rate}"[:50]
    return data


def print_summary(data: dict):
    print(f"\n  Kontrahent:        {data['firm_name']}")
    print(f"  Nr faktury:        {data['invoice_number']}")
    print(f"  Data wystawienia:  {data['invoice_date']}")
    print(f"  Dział:             {data['dzial']}")
    print(f"  Kategoria:         {data['kategoria']}")
    print(f"  Opłacona:          {'tak' if data['oplacona'] else 'nie'}")
    if not data["oplacona"]:
        print(f"  Termin płatności:  {data['payment_date']}")
    print(f"  Kurs EUR/PLN:      {data['kurs_eur']}")
    print(f"  Netto (PLN):       {data['netto']}")
    print(f"  VAT (PLN):         {data['vat']}")
    print(f"  Brutto (PLN):      {data['brutto']}  (źródło: {data['source']})")


def process_file(pdf_path: Path):
    print(f"\n" + "=" * 60 + f"\n📄 ANALIZA (EUR): {pdf_path.name}")

    sys_utils.open_pdf(pdf_path)
    try:
        data = read_invoice(pdf_path)

        suggested_rate, rate_date = nbp_rate.get_nbp_rate("eur", data["invoice_date"])
        rate = ui.ask_exchange_rate(data["netto"], data["vat"], suggested_rate, rate_date)
        data = convert_to_pln(data, rate)

        dzial, kategoria = dk.get_dzial_kategoria(data["firm_name"])
        if dzial is None:
            dzial, kategoria = ui.ask_dzial_kategoria_inne(data["firm_name"])
            dk.update_dzial_kategoria(data["firm_name"], dzial, kategoria)
        data["dzial"], data["kategoria"] = dzial, kategoria

        data["oplacona"] = ui.ask_paid_status_inne(
            data["firm_name"], data["invoice_number"], data["invoice_date"]
        )

        confirm = ui.present_proposal_inne(data)

        if confirm == 'p':
            print(f"⏭️ Pominięto fakturę: {pdf_path.name}")
            return None

        if confirm in ('n', 'nie'):
            corrected = ui.get_manual_corrections_inne(data)
            if corrected == "SKIP":
                print("⏭️ Pominięto fakturę po korekcie.")
                return None
            data.update(corrected)
            dk.update_dzial_kategoria(data["firm_name"], data["dzial"], data["kategoria"])
    finally:
        sys_utils.close_pdf()

    print("\n✅ Zaakceptowano dane faktury:")
    print_summary(data)

    result = rename_file(
        pdf_path, "",
        manual_num=data["invoice_number"],
        manual_firm=data["firm_name"],
        manual_date=data["invoice_date"],
    )
    routing_data = {
        "firm_name": data["firm_name"],
        "invoice_date": data["invoice_date"],
        "payment_date": data["payment_date"],
        "oplacona": data["oplacona"],
        "file_name": result["new_path"].name,
    }
    target_path = file_manager.get_target_path(DEST_DIR, PAYMENT_DIR, MANUAL_DIR, routing_data, "n")
    file_manager.move_file(result["new_path"], target_path)
    print(f"📁 Plik przeniesiony do: {target_path}")

    if db.save_to_faktury_kosztowe(data):
        print("💾 SQL: zapisano w FAKTURY_KOSZTOWE.")

    if file_manager.needs_payment(routing_data):
        data["file_path"] = str(target_path)
        if db.save_to_faktury_do_zaplaty(data):
            print("📧 SQL: dodano do FAKTURY_DO_ZAPLATY.")

    return data


def main():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    PAYMENT_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = list(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"ℹ️ Folder {SOURCE_DIR} jest pusty.")
        return

    print(f"🚀 Odczyt {len(pdf_files)} faktur EUR z {SOURCE_DIR}.")
    accepted = []
    for pdf in pdf_files:
        try:
            data = process_file(pdf)
            if data:
                accepted.append(data)
        except Exception as e:
            print(f"❌ BŁĄD podczas przetwarzania {pdf.name}: {e}")

    print(f"\n🏁 Zakończono. Zaakceptowano i zapisano {len(accepted)}/{len(pdf_files)} faktur.")


if __name__ == "__main__":
    main()
