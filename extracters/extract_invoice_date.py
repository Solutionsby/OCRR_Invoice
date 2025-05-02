from datetime import datetime
import re
import locale

try:
    locale.setlocale(locale.LC_TIME, "pl_PL.UTF-8")
except locale.Error:
    pass

def try_parse_date(raw_date: str) -> str:
    formats = [
        "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d",
        "%d %b %Y", "%d %B %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return "brak-daty"

def extract_invoice_date(text: str) -> str:
    lines = text.splitlines()
    date_regex = r"(\d{2}[./-]\d{2}[./-]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} [a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,9} \d{4})"

    for i, line in enumerate(lines):
        if "data sprzedaży" in line.lower() or "data wystawienia" in line.lower():
            match = re.search(date_regex, line, flags=re.IGNORECASE)
            if not match and i + 1 < len(lines):
                match = re.search(date_regex, lines[i + 1], flags=re.IGNORECASE)
            if match:
                return try_parse_date(match.group(0))

    match = re.search(date_regex, text, flags=re.IGNORECASE)
    if match:
        return try_parse_date(match.group(0))

    return "brak-daty"
