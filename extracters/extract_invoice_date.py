import re
from utils.date_utils import try_parse_date  # <-- IMPORT Z TWOJEGO NOWEGO MODUŁU

def extract_invoice_date(text: str) -> str:
    lines = text.splitlines()
    # Rozszerzony regex, aby łapał różne separatory i nazwy miesięcy
    # Myślnik przesunięty na koniec: [./\s-]
    date_regex = r"(\d{1,2}[./\s-]\d{1,2}[./\s-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2} [a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,9} \d{4})"

    for i, line in enumerate(lines):
        # Szukamy słów kluczowych
        if "data sprzedaży" in line.lower() or "data wystawienia" in line.lower():
            match = re.search(date_regex, line, flags=re.IGNORECASE)
            # Jeśli nie ma w tej samej linii, sprawdź następną (częste w tabelkach)
            if not match and i + 1 < len(lines):
                match = re.search(date_regex, lines[i + 1], flags=re.IGNORECASE)
            
            if match:
                return try_parse_date(match.group(0))

    # Fallback: jeśli nie znaleziono przy słowach kluczowych, weź pierwszą pasującą datę z tekstu
    match = re.search(date_regex, text, flags=re.IGNORECASE)
    if match:
        return try_parse_date(match.group(0))

    return "brak"