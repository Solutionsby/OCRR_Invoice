from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from file_renamer import rename_file

# OCR: konwersja PDF → obrazy
def pdf_to_images(pdf_path: Path):
    return convert_from_path(str(pdf_path))

# OCR: tekst z obrazów
def extract_text_from_images(images):
    full_text = ""
    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image, lang='pol')
        print(f"\n ---- Tekst ze strony {i + 1} ----\n{text}")
        full_text += text + "\n"
    return full_text.strip()

def main():
    pdf_path_str = input("Podaj ścieżkę do pliku PDF: ").strip()
    pdf_path = Path(pdf_path_str)

    if not pdf_path.exists() or not pdf_path.suffix.lower() == ".pdf":
        print("Błąd: Nieprawidłowa ścieżka lub nie jest to plik PDF.")
        return

    print("\n[1] Konwertuję PDF na obrazy...")
    images = pdf_to_images(pdf_path)

    print("[2] Wydobywam tekst za pomocą OCR...")
    extracted_text = extract_text_from_images(images)

    print("[3] Zmieniam nazwę pliku i wyciągam dane...")
    result = rename_file(pdf_path, extracted_text)

    # Wyświetlenie wyciągniętych danych
    print(f"\n➡️ Firma:           {result['firm_name']}")
    print(f"➡️ Nr faktury:      {result['invoice_number']}")
    print(f"➡️ Data faktury:    {result['invoice_date']}")


    print("\nGotowe.")

if __name__ == "__main__":
    main()
