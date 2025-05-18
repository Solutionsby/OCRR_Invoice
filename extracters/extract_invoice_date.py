import re
import locale
from datetime import datetime
from firm_profile_manager import get_profile_for_firm, update_profile

try:
    locale.setlocale(locale.LC_TIME, "pl_PL.UTF-8")
except locale.Error:
    pass

def try_parse_date(raw_date: str) -> dict | None:
    formats = [
        "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d",
        "%d %b %Y", "%d %B %Y"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw_date, fmt)
            return {
                "full": dt.strftime("%Y-%m-%d"),
                "month_year": dt.strftime("%m_%Y")
            }
        except ValueError:
            continue
    return None

def extract_invoice_date(text: str, firm_name: str) -> dict:
    profile = get_profile_for_firm(firm_name)
    lines = text.splitlines()
    date_regex = r"(\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} [a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,9} \d{4})"

    # 1. Jeśli istnieje profil z date_keyword i offsetem – spróbuj
    if profile:
        keyword = profile.get("date_keyword")
        offset = profile.get("date_line_offset", 0)
        if keyword:
            for i, line in enumerate(lines):
                if keyword.lower() in line.lower():
                    target_line = lines[i + offset] if 0 <= i + offset < len(lines) else line
                    match = re.search(date_regex, target_line)
                    if match:
                        parsed = try_parse_date(match.group(0))
                        if parsed:
                            return parsed

    # 2. Fallback: szukaj typowych fraz
    for i, line in enumerate(lines):
        if "data sprzedaży" in line.lower() or "data wystawienia" in line.lower():
            match = re.search(date_regex, line)
            if not match and i + 1 < len(lines):
                match = re.search(date_regex, lines[i + 1])
            if match:
                parsed = try_parse_date(match.group(0))
                if parsed:
                    if not (profile and "date_keyword" in profile):
                        confirm = input(f"📌 Wykryto datę: {parsed['full']} — Czy zapisać ten układ jako wzorzec? (T/n): ").strip().lower()
                        if confirm in ("t", "tak", ""):
                            keyword_match = re.search(r"(data\s+\w+)", line.lower())
                            keyword = keyword_match.group(0).strip().title() if keyword_match else "Data"
                            update_profile(firm_name, {
                                "date_keyword": keyword,
                                "date_line_offset": 0
                            })
                            print(f"💾 Zapisano wzorzec daty: '{keyword}' + offset 0 dla firmy '{firm_name}'")
                    return parsed

    # 3. Fallback: pierwsza data w całym tekście
    match = re.search(date_regex, text)
    if match:
        parsed = try_parse_date(match.group(0))
        if parsed:
            return parsed

    # 4. Pytanie do użytkownika
    print(f"\n❓ Nie znaleziono daty faktury dla firmy: {firm_name}")
    user_date = input("🔧 Podaj datę faktury ręcznie (np. 15.04.2024) lub ENTER aby pominąć: ").strip()
    if user_date:
        parsed = try_parse_date(user_date)
        if parsed:
            keyword = input("🔍 Podaj słowo kluczowe przed datą (np. Data wystawienia): ").strip()
            offset = input("↕️ Ile linii niżej znajduje się data? (np. 0): ").strip()
            try:
                offset_int = int(offset)
            except ValueError:
                offset_int = 0
            if keyword:
                update_profile(firm_name, {
                    "date_keyword": keyword,
                    "date_line_offset": offset_int
                })
                print(f"💾 Zapisano ręcznie wzorzec: '{keyword}' + offset {offset_int} dla firmy '{firm_name}'")
            return parsed

    return {
        "full": "brak-daty",
        "month_year": "brak-daty"
    }
