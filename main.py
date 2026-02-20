import shutil
import platform
import os
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

# Importy Twoich modułów
from config import config_manager as cfg
from config import system_utils as sys_utils
from utils import ui_handler as ui
from utils import file_manager
from utils import knowledge_manager as km  # NOWOŚĆ: Zarządzanie JSONem z działami/kategoriami

# Importy ekstraktorów
from file_renamer import rename_file
from extracters.extract_amounts_by_pattern import extract_invoice_amounts
from extracters.extract_firm_name import extract_firm_name
from extracters.extract_invoice_number import extract_invoice_number
from extracters.extract_invoice_date import extract_invoice_date
from extracters.extract_payment_date import extract_payment_date
from utils import database_manager as db

# --- KONFIGURACJA ŚCIEŻEK ---
if platform.system() == 'Windows':
    BASE_PATH = Path(r"Z:\Twoje_Faktury") 
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    BASE_PATH = Path("./") 

SOURCE_DIR = BASE_PATH / "faktury_surowe"
DEST_DIR = BASE_PATH / "faktury_przetworzone"
PAYMENT_DIR = DEST_DIR / "do_zaplaty"
MANUAL_DIR = PAYMENT_DIR / "do_wpisania_recznie"
MANUAL_PAY_DIR = MANUAL_DIR / "do_zaplaty"

def process_file(pdf_path: Path):
    try:
        print(f"\n" + "="*60 + f"\n📄 ANALIZA: {pdf_path.name}")
        
        # 1. OCR
        path_to_poppler = r'C:\poppler\Library\bin' if platform.system() == 'Windows' else None
        images = convert_from_path(str(pdf_path), poppler_path=path_to_poppler)
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
        
        amounts = extract_invoice_amounts(text, proposed_firm)
        if not isinstance(amounts, dict):
            amounts = {"netto": 0, "vat": 0, "brutto": 0}

        # 3. Interakcja z użytkownikiem
        confirm = ui.present_proposal(proposed_firm, proposed_dept, num, date, pay_date, amounts)
        
        if confirm == 'p':
            print(f"⏭️ Pominięto fakturę: {pdf_path.name}")
            return

        # Wartości domyślne
        final_firm, final_dept, final_num = proposed_firm, proposed_dept, num
        final_date, final_pay_date, final_amounts = date, pay_date, amounts
        final_cat = ""  # Domyślnie pusta kategoria

        if confirm in ['k', 'n', 'nie']:
            sys_utils.open_pdf(pdf_path)
            
            # --- NOWOŚĆ: Wczytujemy bazę wiedzy przed korektą ---
            kb_data = km.load_kb()
            
            # Odbieramy 7 wartości (dodana kategoria na końcu)
            corrections = ui.get_manual_corrections(
                proposed_firm, proposed_dept, num, date, pay_date, amounts,
                is_quick_mode=(confirm == 'k'),
                kb_data=kb_data
            )
            
            if corrections[0] == "SKIP":
                print(f"⏭️ Pominięto fakturę po otwarciu PDF.")
                sys_utils.close_pdf()
                return

            # Rozpakowanie 7 elementów korekty
            final_firm, final_dept, final_num, final_date, final_pay_date, final_amounts, final_cat = corrections
            
            # --- NOWOŚĆ: Aktualizacja bazy wiedzy (nauka systemu) ---
            if confirm != 'k':
                km.update_firm_knowledge(final_firm, final_dept, final_cat)
                # Opcjonalnie: stary config_manager też może zostać zaktualizowany dla kompatybilności
                cfg.update_knowledge_base(scanned_firm, final_firm, final_dept)
                
            sys_utils.close_pdf()
        else:
            # Tryb "Tak" - również uczymy system (nawet jeśli kategoria jest pusta)
            km.update_firm_knowledge(final_firm, final_dept, final_cat)
            cfg.update_knowledge_base(scanned_firm, final_firm, final_dept)

        # 4. Nazewnictwo
        result = rename_file(pdf_path, text, manual_num=final_num, manual_firm=final_firm, manual_date=final_date)
        new_pdf_name = result["new_path"].name 

        # 5. Przygotowanie danych do zapisu
        final_data = {
            "invoice_number": final_num,
            "firm_name": final_firm,
            "invoice_date": final_date,
            "payment_date": final_pay_date,
            "netto": final_amounts.get('netto', 0),
            "vat": final_amounts.get('vat', 0),
            "brutto": final_amounts.get('brutto', 0),
            "dzial": final_dept,
            "kategoria": final_cat,             # NOWOŚĆ: Kategoria trafia do SQL
            "file_name": new_pdf_name
        }

        # --- LOGIKA ZAPISÓW SQL ---
        if confirm != 'k':
            if db.save_to_faktury_kosztowe(final_data):
                print(f"🗄️ Zapisano w tabeli FAKTURY_KOSZTOWE.")
        else:
            print(f"ℹ️ Tryb K: Pominięto zapis w tabeli kosztowej.")

        check_pay_date = str(final_pay_date).lower().strip()
        if check_pay_date != "brak" and check_pay_date != "":
            if db.save_to_faktury_do_zaplaty(final_data):
                print(f"📧 Dodano do bazy płatności SQL.")

        # 6. Segregacja folderów (używa nowej logiki Miesiąc/Dział/Firma)
        target_full_path = file_manager.get_target_path(
            DEST_DIR, PAYMENT_DIR, MANUAL_DIR, final_data, confirm
        )
        
        file_manager.move_file(result["new_path"], target_full_path)
        print(f"✅ Plik przeniesiony do: {target_full_path.parent.name}")

    except Exception as e:
        print(f"❌ BŁĄD podczas przetwarzania {pdf_path.name}: {e}")

def main():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    PAYMENT_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_PAY_DIR.mkdir(parents=True, exist_ok=True)
    
    if not Path("settings.json").exists():
        print("❌ BŁĄD: Brak pliku settings.json!")
        return

    pdf_files = list(SOURCE_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"ℹ️ Folder {SOURCE_DIR} jest pusty.")
        return

    print(f"🚀 Rozpoczynam pracę na {platform.system()}. Znaleziono {len(pdf_files)} plików.")
    for pdf in pdf_files:
        process_file(pdf)
    
    print("\n🏁 Wszystkie zadania wykonane.")

if __name__ == "__main__":
    main()