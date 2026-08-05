from utils.date_utils import try_parse_date
from extracters.extract_payment_info import is_paid

def ask_payment_status_decision(firm, num, date, pay_date, payment_form, brutto):
    """
    Wywoływane tylko gdy KSeF nie podał "Informacja o płatności" i nie dało
    się tego wywnioskować (forma płatności / porównanie dat) — operator musi
    jednoznacznie zdecydować, zamiast żeby program cicho przyjął domyślny stan.
    Pokazujemy te same dane co w głównej propozycji, żeby decyzja nie
    wymagała samego zaglądania do otwartego PDF-u.
    """
    print(f"\n❓ Brak informacji o płatności na fakturze — nie da się jej jednoznacznie wywnioskować.")
    print(f"   🏢 Kontrahent: {firm}")
    print(f"   🔢 Numer:      {num}")
    print(f"   📅 Data FV:    {date}")
    print(f"   ⏳ Termin:     {pay_date}")
    print(f"   💳 Forma:      {payment_form}")
    print(f"   💰 Brutto:     {brutto}")
    answer = input("   Czy faktura jest opłacona? [t/N]: ").strip().lower()
    if answer in ("t", "tak"):
        return "Zapłacono (wskazane ręcznie)"
    return "Brak zapłaty (wskazane ręcznie)"

def present_proposal(firm, num, date, pay_date, payment_status, payment_form, brutto):
    """
    Wyświetla użytkownikowi dane odczytane przez OCR i pobiera decyzję.
    """
    paid_icon = "✅" if is_paid(payment_status) else "❌"
    print("\n" + "-"*40)
    print(f"🏢 KONTRAHENT: {firm}")
    print(f"🔢 NUMER FV:   {num}")
    print(f"📅 DATA FV:    {date}")
    print(f"⏳ TERMIN:     {pay_date}")
    print(f"{paid_icon} PŁATNOŚĆ:   {payment_status}")
    print(f"💳 FORMA:      {payment_form}")
    print(f"💰 BRUTTO:     {brutto}")
    print("-"*40)

    print("\n[T]ak | [N]ie (korekta) | [K]olejkuj do zapłaty | [P]omiń")
    choice = input("👉 Wybór: ").strip().lower()
    return choice

def get_manual_corrections(proposed_firm, num, date, pay_date, payment_status, payment_form, brutto, is_quick_mode=False, kb_data=None):
    """
    Tryb pełnej korekty ręcznej z obsługą Bazy Wiedzy (Kategorie).
    """
    fields = ["firm", "category", "num", "date", "pay_date", "payment_status", "payment_form", "brutto"]

    # Inicjalizacja danych
    data = {
        "firm": proposed_firm,
        "category": "",
        "num": num,
        "date": date,
        "pay_date": pay_date,
        "payment_status": payment_status,
        "payment_form": payment_form,
        "brutto": brutto,
    }

    current_step = 0
    print("\n" + "="*60)
    print(f"🚀 TRYB KOREKTY {'BŁYSKAWICZNEJ' if is_quick_mode else 'RĘCZNEJ'}")
    print("   [Enter] - akceptuj | [b] - cofnij | [p] - pomiń")
    print("="*60)

    while current_step < len(fields):
        field = fields[current_step]

        # --- LOGIKA TRYBU K: Pominięcie Kategorii ---
        if is_quick_mode and field == "category":
            current_step += 1
            continue

        current_val = data[field]
        labels = {
            "firm": "Firma",
            "category": "Kategoria",
            "num": "Numer FV",
            "date": "Data FV",
            "pay_date": "Termin płatności",
            "payment_status": "Status płatności",
            "payment_form": "Forma płatności",
            "brutto": "Kwota brutto",
        }

        # --- SPECJALNA OBSŁUGA KATEGORII (Podpowiedzi) ---
        if field == "category" and kb_data:
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
            return "SKIP", None, None, None, None, None, None, None

        # 2. Obsługa cofania
        if user_input.lower() == 'b':
            if current_step > 0:
                # Przeskocz z powrotem pola ukryte w trybie K
                if is_quick_mode:
                    while current_step > 0 and fields[current_step-1] == "category":
                        current_step -= 1
                current_step -= 1
                print("   << powrót")
                continue
            else:
                print("   ℹ️ Jesteś na początku listy.")
                continue

        # 3. Przetwarzanie zmian (tylko jeśli nieobsłużone wyżej w category)
        if user_input != "" and field != "category":
            if field in ["date", "pay_date"]:
                unified = try_parse_date(user_input)
                data[field] = unified
                if unified != user_input:
                    print(f"   ✨ Poprawiono na: {unified}")
            elif field == "brutto":
                try:
                    data[field] = float(user_input.replace(',', '.'))
                except ValueError:
                    print("   ⚠️ Błędna liczba!")
            else:
                data[field] = user_input

        current_step += 1

    return (data["firm"], data["num"], data["date"], data["pay_date"], data["category"], data["payment_status"], data["payment_form"], data["brutto"])