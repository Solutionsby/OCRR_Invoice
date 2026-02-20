import re
from utils.date_utils import try_parse_date

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
            
    return "brak"