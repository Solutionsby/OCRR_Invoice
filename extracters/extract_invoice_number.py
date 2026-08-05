import re

# W wizualizacji KSeF etykieta "Numer faktury" / "Numer Faktury:" stoi
# samodzielnie w swojej linii, a sam numer jest pierwszą niepustą linią
# poniżej (przed blokiem "Faktura podstawowa" / "Numer KSeF: ...").
LABEL_RE = re.compile(r"numer\s+faktury\s*:?\s*$", re.IGNORECASE)
STOP_PREFIXES = ("faktura podstawowa", "faktura korygująca", "numer ksef")

def extract_invoice_number(text: str, firm_name: str = None) -> str:
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if LABEL_RE.match(line.strip()):
            for next_line in lines[i+1:i+4]:
                candidate = next_line.strip()
                if not candidate:
                    continue
                if candidate.lower().startswith(STOP_PREFIXES):
                    break
                return candidate

    # Fallback: dokumenty spoza KSeF / nietypowe layouty bez etykiety
    patterns = [
        r"FBADS-\d{3}-\d{9}",                               # FBADS
        r"(?:FV|FS|E-FU|FA-MH|F|GRKS|PAYNOW)[/\w-]*[\d]{2,}[/\w-]*", # Prefiksy
        r"202\d/[A-Z0-9/]+",                                # Od roku 202x/
        r"\d{4,}/[A-Z0-9/]+",                                # Zaczynające się od cyfr
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
