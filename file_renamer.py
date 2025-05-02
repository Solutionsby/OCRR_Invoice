from pathlib import Path
from extracters.extract_firm_name import extract_firm_name
from extracters.extract_invoice_date import extract_invoice_date
from extracters.extract_invoice_number import extract_invoice_number
import re


def rename_file(original_path: Path, extracted_text: str):
    base_dir = original_path.parent

    firm_name = extract_firm_name(extracted_text)
    invoice_date = extract_invoice_date(extracted_text)
    invoice_number_path = extract_invoice_number(extracted_text).replace("/", "_").replace("\\", "_").replace(" ", "_")
    invoice_number = extract_invoice_number(extracted_text)


    new_name = f"{firm_name}_{invoice_number_path}_{invoice_date}.pdf"
    new_path = base_dir / new_name

    original_path.rename(new_path)
    print(f"\nZmieniono nazwę pliku na: {new_name}")

    return {
        "new_path": new_path,
        "firm_name": firm_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date
    }
