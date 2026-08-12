import re
from datetime import datetime, timedelta

# Data numeryczna (30.06.2026 / 04/07/2026) albo dzień-miesiąc(słownie)-rok
# w formacie angielskim skrótowym (05-JUL-2026).
DATE_RE = re.compile(
    r"(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{1,2}[-\s][A-Za-z]{3,9}[-\s]\d{4})"
)

EN_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

INVOICE_DATE_LABELS = [
    r"Invoice\s*Date",
    r"Data\s*rachunku",
    r"Data\s*wystawienia",
    r"Data\s*sprzedaży",
    r"Datum",
    r"Data",
]

DUE_DATE_LABELS = [
    r"Payment\s*Due\s*Date",
    r"Termin\s*płatności",
    r"Termin\s*zapłaty",
    r"Płatne\s*do",
    r"Data\s*płatności",
]

IMMEDIATE_DUE_RE = re.compile(
    r"wymagalne\s*natychmiast|natychmiastow|due\s*immediately|payable\s*immediately|"
    r"sofort\b.{0,60}?f[äa]llig",
    re.IGNORECASE,
)

NET_DAYS_RE = re.compile(r"(\d{1,3})\s*dni\s*od\s*(?:dostawy|wystawienia|faktury)", re.IGNORECASE)


def _parse_flexible_date(raw: str) -> str:
    raw = raw.strip()
    # Dzień-miesiąc_słownie-rok, np. "05-JUL-2026" / "05 JUL 2026"
    m = re.match(r"(\d{1,2})[-\s]([A-Za-z]{3,9})[-\s](\d{4})", raw)
    if m:
        day, mon_raw, year = m.groups()
        month = EN_MONTHS.get(mon_raw.lower()[:3])
        if month:
            try:
                return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")
            except ValueError:
                return "brak"
        return "brak"

    # Numeryczna: rozstrzygamy separator, próbujemy dd.mm.yyyy i dd/mm/yyyy
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return "brak"


def _find_date_near_label(text: str, labels) -> str:
    for label in labels:
        match = re.search(label, text, re.IGNORECASE)
        if not match:
            continue
        window = text[match.end(): match.end() + 40]
        date_match = DATE_RE.search(window)
        if date_match:
            parsed = _parse_flexible_date(date_match.group(0))
            if parsed != "brak":
                return parsed
    return "brak"


def extract_invoice_date(text: str) -> str:
    found = _find_date_near_label(text, INVOICE_DATE_LABELS)
    if found != "brak":
        return found
    # Fallback: pierwsza data w tekście.
    match = DATE_RE.search(text)
    return _parse_flexible_date(match.group(0)) if match else "brak"


def extract_due_date(text: str, invoice_date: str) -> str:
    found = _find_date_near_label(text, DUE_DATE_LABELS)
    if found != "brak":
        return found

    if IMMEDIATE_DUE_RE.search(text):
        return invoice_date

    days_match = NET_DAYS_RE.search(text)
    if days_match and invoice_date != "brak":
        try:
            base = datetime.strptime(invoice_date, "%Y-%m-%d")
            return (base + timedelta(days=int(days_match.group(1)))).strftime("%Y-%m-%d")
        except ValueError:
            return "brak"

    return "brak"
