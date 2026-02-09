from config import config_manager as cfg

def present_proposal(firm, dept, num, date, pay_date, amounts):
    print(f"\n" + "—"*50)
    print(f"🔎 PROPOZYCJA SYSTEMU:")
    print(f"   Firma:  {firm} (Dział: {dept if dept else 'BRAK'})")
    print(f"   Numer:  {num} | Data FV: {date} | Płatność: {pay_date}")
    print(f"   Netto:  {amounts.get('netto')} | VAT: {amounts.get('vat')} | Brutto: {amounts.get('brutto')}")
    return input("\n✅ Czy dane są poprawne? (T/n): ").strip().lower()

def get_manual_corrections(proposed_firm, proposed_dept, current_num, current_date, current_pay_date, current_amounts):
    settings = cfg.load_settings()
    dzialy_list = settings.get("dzialy", [])
    
    print("\n🚀 TRYB KOREKTY")
    final_firm = input(f"👉 Firma [{proposed_firm}]: ").strip() or proposed_firm
    final_dept = input(f"👉 Dział [{proposed_dept}]: ").strip() or proposed_dept
    final_date = input(f"👉 Data FV [{current_date}]: ").strip() or current_date
    final_pay_date = input(f"👉 Termin płatności [{current_pay_date}]: ").strip() or current_pay_date
    final_num = input(f"👉 Numer [{current_num}]: ").strip() or current_num
    
    try:
        n_in = input("👉 NETTO: ").replace(" ", "").replace(",", ".")
        v_in = input("👉 VAT:   ").replace(" ", "").replace(",", ".")
        n = float(n_in) if n_in else current_amounts.get('netto', 0)
        v = float(v_in) if v_in else current_amounts.get('vat', 0)
        final_amounts = {'netto': n, 'vat': v, 'brutto': n + v}
    except ValueError:
        print("❌ Błąd formatu liczb! Używam wartości oryginalnych.")
        final_amounts = current_amounts
        
    return final_firm, final_dept, final_num, final_date, final_pay_date, final_amounts