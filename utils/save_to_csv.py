import csv
from pathlib import Path

# Ścieżki do plików
OLD_DB_CSV = Path("dane/baza_glowna.csv")    
PAYMENTS_CSV = Path("dane/do_zaplaty.csv")    

def save_to_csv(data):
    """
    Główna funkcja. 'data' musi być słownikiem przekazanym z main.py
    """
    # Upewniamy się, że data jest słownikiem
    if not isinstance(data, dict):
        print(f"❌ BŁĄD: Oczekiwano słownika, otrzymano {type(data)}")
        return

    # 1. Zapis do starej bazy (bez daty płatności)
    _save_to_old_database(data)
    
    # 2. Zapis do raportu płatności (tylko jeśli jest data zapłaty)
    pay_date = str(data.get("payment_date", "brak")).lower()
    if pay_date != "brak":
        _save_to_payment_report(data)

def _save_to_old_database(data):
    # Nagłówki starej bazy
    headers = ["firm_name", "dzial", "invoice_date", "invoice_number", "netto", "vat", "brutto"]
    
    # Tworzymy czystą kopię danych tylko z tymi polami, które zna stara baza
    row_to_save = {k: data.get(k, "") for k in headers}
    
    file_exists = OLD_DB_CSV.exists()
    
    try:
        with open(OLD_DB_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            # Jeśli plik jest nowy, dopisz nagłówki
            if not file_exists or OLD_DB_CSV.stat().st_size == 0:
                writer.writeheader()
            writer.writerow(row_to_save)
    except Exception as e:
        print(f"❌ Błąd zapisu do {OLD_DB_CSV}: {e}")

def _save_to_payment_report(data):
    # Nagłówki nowej bazy płatności
    headers = ["firm_name", "invoice_number", "payment_date", "brutto"]
    
    # Wybieramy tylko te 4 kolumny
    row_to_save = {
        "firm_name": data.get("firm_name", ""),
        "invoice_number": data.get("invoice_number", ""),
        "payment_date": data.get("payment_date", ""),
        "brutto": data.get("brutto", 0)
    }
    
    file_exists = PAYMENTS_CSV.exists()
    
    try:
        with open(PAYMENTS_CSV, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            # Jeśli plik jest nowy, dopisz nagłówki
            if not file_exists or PAYMENTS_CSV.stat().st_size == 0:
                writer.writeheader()
            writer.writerow(row_to_save)
    except Exception as e:
        print(f"❌ Błąd zapisu do {PAYMENTS_CSV}: {e}")