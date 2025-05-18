from pathlib import Path
from extracters.extract_firm_name import extract_firm_name
from extracters.extract_invoice_number import extract_invoice_number
from extracters.extract_invoice_date import extract_invoice_date

def rename_file(original_path: Path, extracted_text: str):
    base_dir = original_path.parent

    firm_name = extract_firm_name(extracted_text) or "firma"
    invoice_number = extract_invoice_number(extracted_text, firm_name) or "brak_nr"
    date_info = extract_invoice_date(extracted_text, firm_name)
    invoice_date_str = date_info.get("month_year", "brak_dat")
    invoice_date_full = date_info.get("full", "brak_dat")

    safe_number = invoice_number.replace("/", "_").replace("\\", "_").replace(" ", "_")
    safe_firm = "".join(c for c in firm_name if c.isalnum() or c in (' ', '_', '-')).strip()
    new_name = f"{invoice_date_str}_{safe_firm}_{safe_number}.pdf"
    new_path = base_dir / new_name

    # Jeśli plik już istnieje, dodaj sufiks
    counter = 1
    while new_path.exists():
        new_name = f"{safe_firm}_{safe_number}_{invoice_date_str}_{counter}.pdf"
        new_path = base_dir / new_name
        counter += 1

    # 5. Zmiana nazwy pliku
    original_path.rename(new_path)
    print(f"\n✅ Zmieniono nazwę pliku na: {new_name}")

    # 6. Zwracamy dane do dalszego użycia (np. do CSV)
    return {
        "new_path": new_path,
        "firm_name": firm_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date_full  # ← pełna data do zapisu
    }
