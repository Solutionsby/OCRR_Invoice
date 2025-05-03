from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from file_renamer import rename_file
from extracters.extract_amounts_by_pattern import extract_invoice_amounts
from utils.save_to_csv import save_to_csv
import shutil
import re

# Foldery
SOURCE_DIR = Path("./faktury_surowe")
DEST_DIR = Path("./faktury_przetworzone")
DEST_DIR.mkdir(exist_ok=True)

# OCR: konwersja PDF na obrazy
def pdf_to_images(pdf_path: Path):
    return convert_from_path(str(pdf_path))

# OCR: ekstrakcja tekstu z obrazów
def extract_text_from_images(images):
    full_text = ""
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image, lang='pol')
        print(f"\n---- Tekst ze strony {i + 1} ----\n{text}")
        full_text += text + "\n"
    return full_text.strip()

# Przetwarzanie jednego pliku PDF
def process_single_pdf(pdf_path: Path):
    try:
        print(f"\n📄 Przetwarzam plik: {pdf_path.name}")
        images = pdf_to_images(pdf_path)
        extracted_text = extract_text_from_images(images)

        # Zmiana nazwy i wyciągnięcie podstawowych danych
        result = rename_file(pdf_path, extracted_text)

        # Wyciągnięcie kwot
        amounts = extract_invoice_amounts(extracted_text)

        # zapisanie danych do CSV
        save_to_csv({
            "firm_name": result["firm_name"],
            "invoice_date": result["invoice_date"],
            "invoice_number": result["invoice_number"],
            "netto": amounts["netto"],
            "vat": amounts["vat"],
            "brutto": amounts["brutto"]
        })

        # Przeniesienie pliku
        new_named_path = result["new_path"]
        target_path = DEST_DIR / new_named_path.name
        shutil.move(str(new_named_path), target_path)

        # Log danych
        print(f"\n➡️ Firma:         {result['firm_name']}")
        print(f"➡️ Nr faktury:    {result['invoice_number']}")
        print(f"➡️ Data faktury:  {result['invoice_date']}")
        print(f"➡️ Netto:         {amounts['netto']}")
        print(f"➡️ VAT:           {amounts['vat']}")
        print(f"➡️ Brutto:        {amounts['brutto']}")
        print(f"✅ Zapisano jako: {target_path.name}")

    except Exception as e:
        print(f"❌ Błąd przy {pdf_path.name}: {e}")

# Główna pętla
def main():
    pdf_files = list(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print("Brak plików PDF do przetworzenia.")
        return

    for pdf_path in pdf_files:
        process_single_pdf(pdf_path)

if __name__ == "__main__":
    main()
