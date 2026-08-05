import re

def extract_payment_status(text: str) -> str:
    """Odczytuje pole 'Informacja o płatności' z wizualizacji KSeF (np. 'Brak zapłaty')."""
    match = re.search(r"Informacja o płatności:\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else "brak"

def extract_payment_form(text: str) -> str:
    """Odczytuje pole 'Forma płatności' z wizualizacji KSeF (np. 'Przelew')."""
    match = re.search(r"Forma płatności:\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else "brak"

def is_paid(payment_status: str) -> bool:
    """Fakturę uznajemy za opłaconą tylko gdy status wprost o tym mówi (nie zawiera 'brak')."""
    status = (payment_status or "").lower()
    return "zapłac" in status and "brak" not in status
