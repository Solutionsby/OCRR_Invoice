import shutil
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

# Importy Twoich modułów
from config import config_manager as cfg
from config import system_utils as sys_utils
from utils import ui_handler as ui

# Importy ekstraktorów i narzędzi
from file_renamer import rename_file
from extracters.extract_amounts_by_pattern import extract_invoice_amounts
from extracters.extract_firm_name import extract_firm_name
from extracters.extract_invoice_number import extract_invoice_number
from extracters.extract_invoice_date import extract_invoice_date
from extracters.extract_payment_date import extract_payment_date
from utils.save_to_csv import save_to_csv

# --- KONFIGURACJA ŚCIEŻEK ---
SOURCE_DIR = Path("./faktury_surowe")
DEST_DIR = Path("./faktury_przetworzone")
PAYMENT_DIR = DEST_DIR / "do_zaplaty"

def process_file(pdf_path: Path):
    try:
        print(f"\n" + "="*60 + f"\n📄 ANALIZA: {pdf_path.name}")
        
        # 1. OCR (macOS)
        images = convert_from_path(str(pdf_path))
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img, lang='pol') + "\n"
        
        # 2. Pobieranie danych wstępnych
        patterns = cfg.load_patterns()
        scanned_firm = extract_firm_name(text).strip()
        
        proposed_firm, proposed_dept = cfg.get_firm_data(scanned_firm, patterns)
        
        date = extract_invoice_date(text)
        pay_date = extract_payment_date(text)
        num = extract_invoice_number(text, proposed_firm)
        
        # Zabezpieczenie: upewniamy się, że amounts jest słownikiem
        amounts = extract_invoice_amounts(text, proposed_firm)
        if not isinstance(amounts, dict):
            amounts = {"netto": 0, "vat": 0, "brutto": 0}

        # 3. Interakcja z użytkownikiem
        confirm = ui.present_proposal(proposed_firm, proposed_dept, num, date, pay_date, amounts)
        
        final_firm, final_dept, final_num = proposed_firm, proposed_dept, num
        final_date, final_pay_date, final_amounts = date, pay_date, amounts

        if confirm in ['n', 'nie']:
            sys_utils.open_pdf(pdf_path)
            
            # Pobieramy korekty (UI musi zwrócić 6 wartości)
            corrections = ui.get_manual_corrections(
                proposed_firm, proposed_dept, num, date, pay_date, amounts
            )
            (final_firm, final_dept, final_num, final_date, final_pay_date, final_amounts) = corrections
            
            # Nauka: Aktualizacja Aliasów i Działów
            cfg.update_knowledge_base(scanned_firm, final_firm, final_dept)
            sys_utils.close_pdf()
        else:
            # Automatyczne zapamiętanie przypisania firmy do działu
            cfg.update_knowledge_base(scanned_firm, final_firm, final_dept)

        # 4. Nazewnictwo (Format MM_YYYY_FV...)
        result = rename_file(
            pdf_path, 
            text, 
            manual_num=final_num, 
            manual_firm=final_firm, 
            manual_date=final_date
        )
        
        # 5. Zapis do CSV (zabezpieczony przed błędem 'str' has no attribute 'get')
        # Używamy .get(klucz, 0) aby wstawić zero jeśli klucza brakuje
        save_to_csv({
            "firm_name": final_firm,
            "dzial": final_dept,
            "invoice_date": final_date,
            "payment_date": final_pay_date,
            "invoice_number": final_num,
            "netto": final_amounts.get('netto', 0) if isinstance(final_amounts, dict) else 0,
            "vat": final_amounts.get('vat', 0) if isinstance(final_amounts, dict) else 0,
            "brutto": final_amounts.get('brutto', 0) if isinstance(final_amounts, dict) else 0
        })

        # 6. Segregacja folderów
        if final_pay_date.lower() != "brak":
            target_folder = PAYMENT_DIR
        else:
            target_folder = DEST_DIR

        final_path = target_folder / result["new_path"].name
        
        if final_path.exists():
            final_path.unlink()
            
        shutil.move(str(result["new_path"]), final_path)
        print(f"✅ Przetworzono: {final_path.name}")
        print(f"📂 Lokalizacja: {target_folder.name}")

    except Exception as e:
        print(f"❌ Krytyczny błąd podczas przetwarzania {pdf_path.name}: {e}")

def main():
    # Inicjalizacja folderów
    SOURCE_DIR.mkdir(exist_ok=True)
    DEST_DIR.mkdir(exist_ok=True)
    PAYMENT_DIR.mkdir(exist_ok=True)
    
    # Wymagany plik settings.json
    if not Path("settings.json").exists():
        print("❌ BŁĄD: Brak pliku settings.json!")
        return

    pdf_files = list(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"ℹ️ Brak nowych plików w {SOURCE_DIR}")
        return

    print(f"🚀 Start. Znaleziono {len(pdf_files)} plików.")
    for pdf in pdf_files:
        process_file(pdf)
    
    print("\n🏁 Proces zakończony.")

if __name__ == "__main__":
    main()