import re

def extract_payment_date(text):
    """Szuka daty płatności w tekście faktury."""
    # Szukamy słów kluczowych i daty po nich (formaty YYYY-MM-DD, DD.MM.YYYY itp.)
    patterns = [
        r"(?:termin|płatne do|płatność do|data płatności)[:\s]+(\d{2,4}[-./]\d{2}[-./]\d{2,4})",
        r"termin\s+zapłaty[:\s]+(\d{2,4}[-./]\d{2}[-./]\d{2,4})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(".", "-").replace("/", "-")
            
    return "brak"