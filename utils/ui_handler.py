from utils.date_utils import try_parse_date
from utils import database_manager as db
from extracters.extract_payment_info import is_paid
from extracters.inne.amounts import parse_number


def _warn_if_duplicate(numer):
    """
    Numer odczytany przez OCR jest sprawdzony pod kątem duplikatu raz, przed
    prezentacją propozycji (analyze_ksef/analyze_inne/analyze_euro) — gdy
    operator go tu ręcznie poprawi, ten pierwotny odczyt już nie jest
    aktualny, więc sprawdzamy ponownie na nowej wartości.
    """
    matches = db.find_duplicates(numer)
    if not matches:
        return
    print(f"   ⚠️ Możliwy duplikat — numer '{numer}' już jest w bazie:")
    for m in matches:
        plik = f" — {m['plik'].split('/')[-1]}" if m.get("plik") else ""
        print(f"      {m['tabela']}: {m['kontrahent']}{plik}")

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
                if field == "num":
                    _warn_if_duplicate(data[field])

        current_step += 1

    return (data["firm"], data["num"], data["date"], data["pay_date"], data["category"], data["payment_status"], data["payment_form"], data["brutto"])


# --- FAKTURY EURO ---

def ask_exchange_rate(eur_netto, eur_vat, suggested_rate=None, rate_date=None):
    """
    Kurs EUR/PLN — domyślnie proponowany z NBP (dzień przed datą wystawienia,
    zgodnie z zasadą podatkową); [Enter] akceptuje, albo operator wpisuje
    własną wartość. Gdy NBP nie odpowiedział (brak sieci/danych),
    suggested_rate jest None i wymagane jest wpisanie kursu ręcznie.
    """
    print(f"\n💱 Kwoty odczytane w EUR — Netto: {eur_netto}  VAT: {eur_vat}")
    if suggested_rate is None:
        print("   ⚠️ Nie udało się pobrać kursu z NBP — wpisz go ręcznie.")
        prompt = "   Kurs EUR/PLN: "
    else:
        print(f"   Kurs NBP z {rate_date}: {suggested_rate}")
        prompt = f"   Kurs EUR/PLN [Enter = {suggested_rate}]: "

    while True:
        raw = input(prompt).strip()
        if raw == "" and suggested_rate is not None:
            return suggested_rate
        rate = parse_number(raw)
        if rate > 0:
            return rate
        print("   ⚠️ Podaj poprawny, dodatni kurs.")


# --- FAKTURY SPOZA KSeF ("inne") ---
# Te faktury nie mają żadnej etykiety statusu płatności (w przeciwieństwie do
# KSeF), więc w odróżnieniu od present_proposal/ask_payment_status_decision
# operator jest pytany wprost, zanim jeszcze zobaczy pełną propozycję —
# od tej odpowiedzi zależy, czy w ogóle pokazujemy termin płatności.

def ask_dzial_kategoria_inne(firm_name):
    """
    Wywoływane tylko gdy firma jeszcze nie jest znana w
    json/dzial_kategoria.json — raz podana wartość jest zapisywana i przy
    kolejnych fakturach tego kontrahenta nie trzeba już pytać.
    """
    print(f"\n❓ Nieznany kontrahent w bazie dział/kategoria: {firm_name}")
    dzial = input("   Dział: ").strip() or "brak"
    kategoria = input("   Kategoria: ").strip() or "brak"
    return dzial, kategoria


def ask_paid_status_inne(firm, num, date):
    print(f"\n❓ Brak informacji o statusie płatności na tej fakturze.")
    print(f"   🏢 Kontrahent: {firm}")
    print(f"   🔢 Numer:      {num}")
    print(f"   📅 Data FV:    {date}")
    answer = input("   Czy faktura jest już opłacona? [t/N]: ").strip().lower()
    return answer in ("t", "tak")


def present_proposal_inne(data):
    """
    data: firm_name, invoice_number, invoice_date, payment_date, netto, vat,
    brutto, oplacona (bool, ustalone wcześniej przez ask_paid_status_inne).
    """
    paid_icon = "✅" if data["oplacona"] else "❌"
    print("\n" + "-" * 40)
    print(f"🏢 KONTRAHENT: {data['firm_name']}")
    print(f"🔢 NUMER FV:   {data['invoice_number']}")
    print(f"📅 DATA FV:    {data['invoice_date']}")
    print(f"🏷️ DZIAŁ:      {data['dzial']}")
    print(f"📂 KATEGORIA:  {data['kategoria']}")
    print(f"{paid_icon} OPŁACONA:  {'tak' if data['oplacona'] else 'nie'}")
    if not data["oplacona"]:
        print(f"⏳ TERMIN:     {data['payment_date']}")
    print(f"💵 NETTO:      {data['netto']}")
    print(f"🧾 VAT:        {data['vat']}")
    print(f"💰 BRUTTO:     {data['brutto']}  (źródło: {data['source']})")
    print("-" * 40)

    print("\n[T]ak | [N]ie (korekta) | [P]omiń")
    return input("👉 Wybór: ").strip().lower()


def get_manual_corrections_inne(data):
    """
    Korekta ręczna pól faktury spoza KSeF. Pole 'pay_date' pomijane, gdy
    operator oznaczył fakturę jako opłaconą (wtedy termin jest nieistotny).
    Brutto nigdy nie jest wpisywane ręcznie — zawsze przeliczane na końcu
    jako netto+vat, zgodnie z zasadą całego etapu odczytu.
    """
    fields = ["firm", "num", "date", "dzial", "kategoria", "paid", "pay_date", "netto", "vat"]
    labels = {
        "firm": "Kontrahent",
        "num": "Numer FV",
        "date": "Data FV",
        "dzial": "Dział",
        "kategoria": "Kategoria",
        "paid": "Opłacona? (t/n)",
        "pay_date": "Termin płatności",
        "netto": "Kwota netto",
        "vat": "Kwota VAT",
    }
    current = {
        "firm": data["firm_name"],
        "num": data["invoice_number"],
        "date": data["invoice_date"],
        "dzial": data["dzial"],
        "kategoria": data["kategoria"],
        "paid": data["oplacona"],
        "pay_date": data["payment_date"],
        "netto": data["netto"],
        "vat": data["vat"],
    }

    step = 0
    print("\n" + "=" * 60)
    print("🚀 TRYB KOREKTY RĘCZNEJ (faktura spoza KSeF)")
    print("   [Enter] - akceptuj | [b] - cofnij | [p] - pomiń")
    print("=" * 60)

    while step < len(fields):
        field = fields[step]

        if field == "pay_date" and current["paid"]:
            step += 1
            continue

        display_val = ("tak" if current["paid"] else "nie") if field == "paid" else current[field]
        user_input = input(f"👉 {labels[field]} [{display_val}]: ").strip()

        if user_input.lower() == 'p':
            return "SKIP"

        if user_input.lower() == 'b':
            if step > 0:
                step -= 1
                if fields[step] == "pay_date" and current["paid"]:
                    step -= 1
                print("   << powrót")
                continue
            print("   ℹ️ Jesteś na początku listy.")
            continue

        if user_input != "":
            if field == "date" or field == "pay_date":
                unified = try_parse_date(user_input)
                current[field] = unified
                if unified != user_input:
                    print(f"   ✨ Poprawiono na: {unified}")
            elif field == "paid":
                current[field] = user_input.lower() in ("t", "tak")
            elif field in ("netto", "vat"):
                current[field] = parse_number(user_input)
            else:
                current[field] = user_input
                if field == "num":
                    _warn_if_duplicate(current[field])

        step += 1

    brutto = round(current["netto"] + current["vat"], 2)
    return {
        "firm_name": current["firm"],
        "invoice_number": current["num"],
        "invoice_date": current["date"],
        "dzial": current["dzial"],
        "kategoria": current["kategoria"],
        "oplacona": current["paid"],
        "payment_date": "brak" if current["paid"] else current["pay_date"],
        "netto": current["netto"],
        "vat": current["vat"],
        "brutto": brutto,
        "source": "korekta_reczna",
    }