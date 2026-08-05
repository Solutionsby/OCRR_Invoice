from utils.date_utils import try_parse_date

def present_proposal(firm, dept, num, date, pay_date, amounts):
    """
    Wyświetla użytkownikowi dane odczytane przez OCR i pobiera decyzję.
    """
    print("\n" + "-"*40)
    print(f"🏢 KONTRAHENT: {firm}")
    print(f"📁 DZIAŁ:      {dept}")
    print(f"🔢 NUMER FV:   {num}")
    print(f"📅 DATA FV:    {date}")
    print(f"⏳ TERMIN:     {pay_date}")
    print(f"💰 KWOTY:      Netto: {amounts.get('netto')} | VAT: {amounts.get('vat')} | Brutto: {amounts.get('brutto')}")
    print("-"*40)
    
    print("\n[T]ak | [N]ie (korekta) | [K]olejkuj do zapłaty (bez działu) | [P]omiń")
    choice = input("👉 Wybór: ").strip().lower()
    return choice

def get_manual_corrections(proposed_firm, proposed_dept, num, date, pay_date, amounts, is_quick_mode=False, kb_data=None):
    """
    Tryb pełnej korekty ręcznej z obsługą Bazy Wiedzy (Działy i Kategorie).
    """
    # Dodaliśmy 'category' i 'kaucja' do listy pól
    fields = ["firm", "dept", "category", "num", "date", "pay_date", "netto", "vat", "kaucja", "brutto"]
    
    try:
        n_val = float(str(amounts.get('netto', 0)).replace(',', '.'))
        v_val = float(str(amounts.get('vat', 0)).replace(',', '.'))
        b_val = float(str(amounts.get('brutto', 0)).replace(',', '.'))
        k_val = float(str(amounts.get('kaucja', 0)).replace(',', '.'))
    except ValueError:
        n_val, v_val, b_val, k_val = 0.0, 0.0, 0.0, 0.0

    # Inicjalizacja danych
    data = {
        "firm": proposed_firm,
        "dept": "TYLKO PŁATNOŚĆ" if is_quick_mode else proposed_dept,
        "category": "", 
        "num": num,
        "date": date,
        "pay_date": pay_date,
        "netto": n_val,
        "vat": v_val,
        "brutto": b_val,
        "kaucja": k_val,
    }

    current_step = 0
    print("\n" + "="*60)
    print(f"🚀 TRYB KOREKTY {'BŁYSKAWICZNEJ (BEZ DZIAŁU)' if is_quick_mode else 'RĘCZNEJ'}")
    print("   [Enter] - akceptuj | [b] - cofnij | [p] - pomiń")
    print("="*60)

    while current_step < len(fields):
        field = fields[current_step]
        
        # --- LOGIKA TRYBU K: Pominięcie Działu i Kategorii ---
        if is_quick_mode and field in ["dept", "category"]:
            current_step += 1
            continue

        current_val = data[field]
        labels = {
            "firm": "Firma", 
            "dept": "Dział", 
            "category": "Kategoria",
            "num": "Numer FV", 
            "date": "Data FV", 
            "pay_date": "Termin płatności", 
            "netto": "Kwota Netto", 
            "vat": "Kwota VAT", 
            "brutto": "Kwota Brutto",
            "kaucja": "Kaucja",
        }

        # --- SPECJALNA OBSŁUGA DZIAŁU (Lista numerowana) ---
        if field == "dept" and kb_data:
            available_depts = kb_data.get("dostepne_dzialy", [])
            print(f"\n👉 Wybierz Dział (wpisz numer lub nową nazwę) [Obecny: {current_val}]:")
            for i, d in enumerate(available_depts, 1):
                print(f"   [{i}] {d}")
            user_input = input("   Wybór: ").strip()

            if user_input.isdigit() and 1 <= int(user_input) <= len(available_depts):
                data[field] = available_depts[int(user_input)-1]
            elif user_input != "":
                data[field] = user_input
        
        # --- SPECJALNA OBSŁUGA KATEGORII (Podpowiedzi) ---
        elif field == "category" and kb_data:
            firm_info = kb_data.get("historia_firm", {}).get(data["firm"], {})
            known_cats = firm_info.get("kategorie", [])
            if known_cats:
                print(f"\n💡 Sugerowane kategorie dla {data['firm']}: {', '.join(known_cats)}")
            user_input = input(f"👉 Kategoria [brak]: ").strip()
            data[field] = user_input

        # --- STANDARDOWE POLA ---
        else:
            user_input = input(f"👉 {labels[field]} [{current_val}]: ").strip()

        # 1. Obsługa pominięcia
        if user_input.lower() == 'p':
            return "SKIP", None, None, None, None, None, None
        
        # 2. Obsługa cofania
        if user_input.lower() == 'b':
            if current_step > 0:
                # Przeskocz z powrotem pola ukryte w trybie K
                if is_quick_mode:
                    while current_step > 0 and fields[current_step-1] in ["dept", "category"]:
                        current_step -= 1
                current_step -= 1
                print("   << powrót")
                continue
            else:
                print("   ℹ️ Jesteś na początku listy.")
                continue

        # 3. Przetwarzanie zmian (tylko jeśli nieobsłużone wyżej w dept/category)
        if user_input != "" and field not in ["dept", "category"]:
            if field in ["netto", "vat", "brutto", "kaucja"]:
                try:
                    data[field] = float(user_input.replace(',', '.'))
                except ValueError:
                    print("   ⚠️ Błędna liczba!")
            
            elif field in ["date", "pay_date"]:
                unified = try_parse_date(user_input)
                data[field] = unified
                if unified != user_input:
                    print(f"   ✨ Poprawiono na: {unified}")
            else:
                data[field] = user_input

        # 4. Automatyczne Brutto = netto + vat + kaucja
        if field in ["netto", "vat", "kaucja"]:
            data["brutto"] = round(
                float(data["netto"]) + float(data["vat"]) + float(data["kaucja"]), 2
            )
        
        current_step += 1

    final_amounts = {
        "netto": data["netto"],
        "vat": data["vat"],
        "brutto": data["brutto"],
        "kaucja": data["kaucja"],
    }

    # Zwracamy teraz 7 wartości (dodana kategoria na końcu)
    return (data["firm"], data["dept"], data["num"], data["date"], data["pay_date"], final_amounts, data["category"])