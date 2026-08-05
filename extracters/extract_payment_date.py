import re
from utils.date_utils import try_parse_date

DATE_RE = r"(\d{1,2}[./\s-]\d{1,2}[./\s-]\d{2,4}|\d{4}-\d{2}-\d{2})"

def extract_payment_date(text):
    """Szuka daty płatności i wymusza format YYYY-MM-DD."""
    patterns = [
    # Myślnik przesunięty na koniec: [./\s-]
    r"(?:termin|płatne do|płatność do|data płatności)[:\s]+(\d{1,2}[./\s-]\d{1,2}[./\s-]\d{2,4})",
    r"termin\s+zapłaty[:\s]+(\d{1,2}[\s]\w+[\s]\d{4})"
]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found_raw = match.group(1).strip()
            return try_parse_date(found_raw)

    # KSeF: etykieta "Termin płatności" stoi samodzielnie w swojej linii,
    # a sama data pojawia się kilka linii niżej (osobny blok w wizualizacji PDF).
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "termin płatności" in line.lower():
            for next_line in lines[i + 1:i + 5]:
                match = re.search(DATE_RE, next_line)
                if match:
                    return try_parse_date(match.group(0))

    return "brak"