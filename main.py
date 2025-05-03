from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from file_renamer import rename_file
import shutil

# Folder wejściowy i wyjściowy
SOURCE_DIR = Path("./faktury_surowe")
DEST_DIR = Path("./faktury_przetworzone")
DEST_DIR.mkdir(exist_ok=True)

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

def process_single_pdf(pdf_path: Path):
    try:
        print(f"\n📄 Przetwarzam plik: {pdf_path.name}")
        images = pdf_to_images(pdf_path)
        extracted_text = extract_text_from_images(images)
        result = rename_file(pdf_path, extracted_text)

        # Przenieś plik do folderu przetworzonych
        target_path = DEST_DIR / result["new_path"].name
        shutil.move(str(result["new_path"]), target_path)

        print(f"✅ Gotowe: {target_path.name}")

    except Exception as e:
        print(f"❌ Błąd przy {pdf_path.name}: {e}")

def main():
    pdf_files = list(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print("Brak plików PDF do przetworzenia.")
        return

    for pdf_path in pdf_files:
        process_single_pdf(pdf_path)

if __name__ == "__main__":
    main()
