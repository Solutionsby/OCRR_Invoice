import csv
from datetime import datetime, timedelta
from pathlib import Path

# Ścieżka do Twojego dedykowanego pliku
PAYMENTS_CSV = Path("dane/do_zaplaty.csv")

def get_date_range():
    """Zwraca zakres dat: od dziś do za 7 dni."""
    today = datetime.now().date()
    end_date = today + timedelta(days=7)
    return today, end_date

def load_upcoming_payments():
    """Wczytuje faktury i filtruje te z terminem w nadchodzącym tygodniu."""
    if not PAYMENTS_CSV.exists():
        return [], 0
    
    start_date, end_date = get_date_range()
    upcoming_list = []
    total_amount = 0.0
    
    with open(PAYMENTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parsowanie daty (zakładamy format YYYY-MM-DD z ekstraktora)
                p_date = datetime.strptime(row["payment_date"], "%Y-%m-%d").date()
                
                # Sprawdzamy czy mieści się w zakresie 7 dni
                if start_date <= p_date <= end_date:
                    row["brutto"] = float(row["brutto"]) # konwersja na liczbę do obliczeń
                    upcoming_list.append(row)
                    total_amount += row["brutto"]
            except (ValueError, KeyError):
                continue # Pomiń błędne wpisy lub nagłówki
                
    # Sortujemy listę według daty płatności (najbliższe najpierw)
    upcoming_list.sort(key=lambda x: x["payment_date"])
    return upcoming_list, total_amount

def generate_report():
    """Generuje wizualny raport w terminalu."""
    start, end = get_date_range()
    payments, total = load_upcoming_payments()
    
    print(f"\n" + "="*70)
    print(f"📅 RAPORT PŁATNOŚCI: {start} do {end}")
    print(f"="*70)
    
    if not payments:
        print("  Brak faktur do zapłaty w nadchodzącym tygodniu. 😎")
    else:
        print(f"{'TERMIN':<12} | {'FIRMA':<25} | {'NR FAKTURY':<15} | {'KWOTA'}")
        print("-" * 70)
        
        for p in payments:
            print(f"{p['payment_date']:<12} | {p['firm_name'][:25]:<25} | {p['invoice_number'][:15]:<15} | {p['brutto']:>8.2f} zł")
            
        print("-" * 70)
        print(f"{'SUMA DO PRZELANIA:':<55} {total:>8.2f} zł")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    generate_report()