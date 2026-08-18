from pathlib import Path
import re
from extracters.extract_firm_name import extract_firm_name
from extracters.extract_invoice_date import extract_invoice_date
from extracters.extract_invoice_number import extract_invoice_number


def sanitize_invoice_number(invoice_number) -> str:
    """
    Ta sama reguła, którą rename_file() stosuje do numeru faktury przy
    budowaniu nazwy pliku (MM_YYYY_FV_Numer_Firma.pdf) — wydzielona, żeby
    core/monthly_report.py mogło dopasować wiersze FAKTURY_KOSZTOWE do
    plików PDF po nazwie, bez duplikowania (i ewentualnego rozjechania się)
    tej samej logiki czyszczenia znaków.
    """
    return str(invoice_number).replace("/", "_").replace("\\", "_").replace(" ", "_").replace(":", "_")


def rename_file(original_path: Path, extracted_text: str, manual_num=None, manual_firm=None, manual_date=None):
    base_dir = original_path.parent
    
    # 1. Pobieranie Firmy
    firm_name = manual_firm if manual_firm else extract_firm_name(extracted_text)
    
    # 2. Pobieranie Daty (używamy manualnej lub szukamy automatem)
    # Zakładamy, że format to YYYY-MM-DD (np. 2025-12-08)
    raw_date = manual_date if manual_date else extract_invoice_date(extracted_text)
    
    # Hardkodowanie wyciągania Miesiąca i Roku
    # Szukamy wszystkich ciągów cyfr w dacie
    date_parts = re.findall(r'\d+', str(raw_date))
    
    if len(date_parts) >= 3:
        # Skoro wiemy, że format to Rok-Miesiąc-Dzień:
        year = date_parts[0]  # Pierwszy element to Rok (YYYY)
        month = date_parts[1] # Drugi element to Miesiąc (MM)
        formatted_date = f"{month}_{year}"
    elif len(date_parts) == 2:
        # Jeśli jakimś cudem dostałby tylko Rok i Miesiąc
        formatted_date = f"{date_parts[1]}_{date_parts[0]}"
    else:
        formatted_date = "00_0000"

    # 3. Pobieranie Numeru
    invoice_number = manual_num if manual_num else extract_invoice_number(extracted_text, firm_name)

    # Czyszczenie nazw do bezpiecznego zapisu pliku (usuwanie znaków zakazanych w Windows/Mac)
    safe_num = sanitize_invoice_number(invoice_number)
    safe_firm = str(firm_name).replace(" ", "_").replace(".", "").replace('"', "")

    # Nowa nazwa: MM_YYYY_FV_Numer_Firma.pdf
    new_name = f"{formatted_date}_FV_{safe_num}_{safe_firm}.pdf"
    new_path = base_dir / new_name

    # Zmiana nazwy pliku na dysku
    try:
        original_path.rename(new_path)
    except FileExistsError:
        # Jeśli plik o tej nazwie istnieje, dodaj przyrostek, by nie nadpisać
        new_name = f"{formatted_date}_FV_{safe_num}_{safe_firm}_nowy.pdf"
        new_path = base_dir / new_name
        original_path.rename(new_path)

    return {
        "new_path": new_path,
        "firm_name": firm_name,
        "invoice_number": invoice_number,
        "invoice_date": raw_date # W CSV zostaje pełna data YYYY-MM-DD
    }