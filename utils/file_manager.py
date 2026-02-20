import shutil
from pathlib import Path
from datetime import datetime

def get_target_path(base_dest_dir, payment_dir, manual_dir, data, confirm_mode):
    new_name = data['file_name']
    pay_date = str(data['payment_date']).lower().strip()
    dept = data['dzial']
    firm = data['firm_name']
    inv_date = data['invoice_date'] # Oczekujemy formatu YYYY-MM-DD

    # --- LOGIKA SEGREGACJI ---

    # 1. Tryb K (Zawsze do wpisania ręcznie)
    if confirm_mode == 'k':
        if pay_date != "brak" and pay_date != "":
            target_folder = manual_dir / "do_zaplaty"
        else:
            target_folder = manual_dir
    
    # 2. Jest data płatności (Tryb T lub N) -> Do zapłaty (tymczasowo)
    elif pay_date != "brak" and pay_date != "":
        target_folder = payment_dir
    
    # 3. Brak daty płatności (Gotówkowe/Opłacone) -> ARCHIWUM (Miesiąc-Dział-Firma)
    else:
        # Wyciągamy miesiąc i rok z daty wystawienia
        try:
           month_num = inv_date.split("-")[1]
        except (IndexError, AttributeError):
            month_num = "00_Nieznany"

        target_folder = base_dest_dir / month_num / dept / firm

    # Tworzenie całej ścieżki (parents=True utworzy wszystkie podfoldery na raz)
    target_folder.mkdir(parents=True, exist_ok=True)
    return target_folder / new_name

def move_file(source_path, target_path):
    if target_path.exists():
        target_path.unlink()
    shutil.move(str(source_path), target_path)
    return target_path