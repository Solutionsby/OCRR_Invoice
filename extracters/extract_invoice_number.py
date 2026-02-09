import re

def extract_invoice_number(text: str, firm_name: str = None) -> str:
    # Ujednolicona lista wzorców na podstawie Twoich przykładów
    patterns = [
        r"FBADS-\d{3}-\d{9}",                               # FBADS
        r"(?:FV|FS|E-FU|FA-MH|F|GRKS|PAYNOW)[/\w-]*[\d]{2,}[/\w-]*", # Prefiksy
        r"202\d/[A-Z0-9/]+",                                # Od roku 202x/
        r"\d{4,}/[A-Z0-9/]+",                               # Zaczynające się od cyfr
        r"[\d]{3,}/[\w/]+(?:FVS|KPRE|BS)",                  # Z końcówkami
        r"F\d{10,}",                                        # Bardzo długie F...
        r"\w+/\d{2}/\d{4}"                                  # Standardowe daty/numery
    ]
    
    found_numbers = []
    for p in patterns:
        matches = re.findall(p, text, re.IGNORECASE)
        for m in matches:
            num = m.strip()
            if len(num) > 4:
                found_numbers.append(num)

    return found_numbers[0] if found_numbers else "brak-nr"