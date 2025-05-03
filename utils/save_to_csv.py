import csv
from pathlib import Path

CSV_PATH = Path("dane/faktury.csv")
CSV_PATH.parent.mkdir(exist_ok=True)

def save_to_csv(data: dict):
    headers = ["firm_name", "invoice_date", "invoice_number", "netto", "vat", "brutto"]

    file_exists = CSV_PATH.exists()
    
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "firm_name": data.get("firm_name"),
            "invoice_date": data.get("invoice_date"),
            "invoice_number": data.get("invoice_number"),
            "netto": data.get("netto"),
            "vat": data.get("vat"),
            "brutto": data.get("brutto"),
        })
