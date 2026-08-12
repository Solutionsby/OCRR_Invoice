import re

LABEL_RE = re.compile(
    r"(?:numer\s+faktury|numer\s+rachunku|invoice\s*(?:number|no\.?|#)|nr\s*faktury|faktura\s*nr|"
    r"rachunek\s*nr|rechnungsnummer|r\.?\s*nr\.?)"
    r"\s*[:\s]*([A-Za-z0-9][A-Za-z0-9\-/]*)",
    re.IGNORECASE,
)


def extract_invoice_number(text: str) -> str:
    match = LABEL_RE.search(text)
    return match.group(1) if match else "brak-nr"
