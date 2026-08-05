import shutil
from pathlib import Path
from datetime import datetime

def needs_payment(data):
    """
    Faktura wymaga jeszcze zapłaty tylko gdy KSeF nie zgłasza jej jako
    opłaconej i ma podany termin płatności. Ta sama reguła decyduje o tym,
    czy plik trafia do folderu "do_zaplaty" i czy zapisujemy go w bazie
    FAKTURY_DO_ZAPLATY (patrz main.py).
    """
    pay_date = str(data.get('payment_date', 'brak')).lower().strip()
    is_paid = data.get('oplacona', False)
    return not is_paid and pay_date not in ("brak", "")

def get_target_path(base_dest_dir, payment_dir, manual_dir, data, confirm_mode):
    new_name = data['file_name']
    firm = data['firm_name']
    inv_date = data['invoice_date'] # Oczekujemy formatu YYYY-MM-DD
    payment_needed = needs_payment(data)

    # --- LOGIKA SEGREGACJI ---
    # Status "opłacona" z KSeF ma priorytet nad samym terminem płatności —
    # opłacona faktura trafia od razu do archiwum, niezależnie od terminu.

    # 1. Tryb K (Zawsze do wpisania ręcznie)
    if confirm_mode == 'k':
        if payment_needed:
            target_folder = manual_dir / "do_zaplaty"
        else:
            target_folder = manual_dir

    # 2. Jest termin płatności i faktura nieopłacona (Tryb T lub N) -> Do zapłaty (tymczasowo)
    elif payment_needed:
        target_folder = payment_dir

    # 3. Opłacona lub brak terminu płatności -> ARCHIWUM (Miesiąc-Firma)
    else:
        # Wyciągamy miesiąc i rok z daty wystawienia
        try:
           month_num = inv_date.split("-")[1]
        except (IndexError, AttributeError):
            month_num = "00_Nieznany"

        target_folder = base_dest_dir / month_num / firm

    # Tworzenie całej ścieżki (parents=True utworzy wszystkie podfoldery na raz)
    target_folder.mkdir(parents=True, exist_ok=True)
    return target_folder / new_name

def move_file(source_path, target_path):
    if target_path.exists():
        target_path.unlink()
    shutil.move(str(source_path), target_path)
    return target_path