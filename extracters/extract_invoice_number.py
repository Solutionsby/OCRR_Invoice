import re
from firm_profile_manager import get_profile_for_firm, update_profile

def extract_invoice_number(text: str, firm_name: str) -> str:
    profile = get_profile_for_firm(firm_name)
    lines = text.splitlines()

    # Domyślne wzorce, jeśli brak podpowiedzi
    patterns = [
        r"F\s*/\s*\d+/\d+/\d+",
        r"FS/\d+/\d+/\d+",
        r"E-[A-Z]{1,5}[\d/]{4,}",
        r"VAT\s*\d+/\d+/\d+" 
    ]

    # Wzorce z profilu (jeśli są)
    if profile:
        hint = profile.get("invoice_number_hint")
        if isinstance(hint, str):
            patterns.insert(0, rf"{re.escape(hint)}[\w\-/.]+")
        elif isinstance(hint, list):
            patterns = [rf"{re.escape(p)}[\w\-/.]+" for p in hint] + patterns

    # Szukanie numeru faktury
    for line in lines:
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(0)

    # Jeśli nie znaleziono – pytamy użytkownika
    print(f"\n❓ Nie znaleziono numeru faktury dla firmy: {firm_name}")
    user_input = input("🔧 Podaj numer faktury ręcznie (np. FV 1/04/2025): ").strip()

    if user_input:
        prefix_match = re.match(r"[A-Z]{1,5}[ /-]?", user_input.upper())
        prefix = prefix_match.group(0) if prefix_match else user_input[:2]

        update_profile(firm_name, {"invoice_number_hint": prefix})
        print(f"💾 Zapisano wzorzec numeru '{prefix}' dla firmy '{firm_name}'")
        return user_input


    return "brak-nr"
