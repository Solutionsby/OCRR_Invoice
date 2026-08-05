import csv
from pathlib import Path

# Ścieżki do plików - Upewniamy się, że foldery istnieją
OLD_DB_CSV = Path("dane/baza_glowna.csv")    
PAYMENTS_CSV = Path("dane/do_zaplaty.csv")    

def save_to_csv(data):
    """
    Główna funkcja rozdzielająca dane do dwóch baz.
    """
    # Upewniamy się, że folder 'dane' istnieje
    OLD_DB_CSV.parent.mkdir(parents=True, exist_ok=True)

    if not isinstance(data, dict):
        print(f"❌ BŁĄD: Oczekiwano słownika, otrzymano {type(data)}")
        return

    # 1. Zapis do głównej bazy historycznej
    _save_to_old_database(data)
    
    # 2. Zapis do raportu płatności (tylko jeśli jest data zapłaty)
    pay_date = str(data.get("payment_date", "brak")).lower()
    if pay_date != "brak":
        _save_to_payment_report(data)

def _save_to_old_database(data):
    # Nagłówki starej bazy (zgodnie z Twoim wzorem)
    headers = ["firm_name", "invoice_date", "invoice_number", "netto", "vat", "brutto"]
    
    row_to_save = {k: data.get(k, "") for k in headers}
    file_exists = OLD_DB_CSV.exists()
    
    try:
        # Używamy utf-8-sig, aby polskie znaki (ą, ć, ł) otwierały się poprawnie w Excelu
        # Dodajemy delimiter=';', jeśli Twój Excel tego wymaga (standard w PL)
        with open(OLD_DB_CSV, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=';')
            if not file_exists or OLD_DB_CSV.stat().st_size == 0:
                writer.writeheader()
            writer.writerow(row_to_save)
        print(f"💾 Dopisano do bazy głównej: {data.get('firm_name')}")
    except Exception as e:
        print(f"❌ Błąd zapisu do {OLD_DB_CSV}: {e}")

def _save_to_payment_report(data):
    # Nagłówki raportu płatności (tylko 4 kluczowe kolumny)
    headers = ["firm_name", "invoice_number", "payment_date", "brutto"]
    
    row_to_save = {
        "firm_name": data.get("firm_name", ""),
        "invoice_number": data.get("invoice_number", ""),
        "payment_date": data.get("payment_date", ""),
        "brutto": data.get("brutto", 0)
    }
    
    file_exists = PAYMENTS_CSV.exists()
    
    try:
        with open(PAYMENTS_CSV, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=';')
            if not file_exists or PAYMENTS_CSV.stat().st_size == 0:
                writer.writeheader()
            writer.writerow(row_to_save)
        print(f"💰 Dodano do listy płatności: {data.get('payment_date')}")
    except Exception as e:
        print(f"❌ Błąd zapisu do {PAYMENTS_CSV}: {e}")