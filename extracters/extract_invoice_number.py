import re

def extract_invoice_number(text: str) -> str:
    # Normalizujemy tekst, np. usuwamy podwójne spacje
    text = re.sub(r"\s+", " ", text)

    # Szukamy wzorców numerów faktur z typowymi prefiksami
    patterns = [
        r"(F\s*/\s*\d+/\d+/\d+)",
        r"(?:FS/\d+/\d+/\d+)",
        r"E-[A-Z]{1,5}[\d/]{4,}",
        r"(?:VAT\s*\d+/\d+/\d+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            # Usuwamy zbędne spacje w dopasowanym ciągu
            return re.sub(r"\s+", "", match.group(0))

    return "brak-nr"