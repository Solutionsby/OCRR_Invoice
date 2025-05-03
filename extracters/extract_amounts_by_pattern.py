import re

def extract_invoice_amounts(text: str) -> dict:
    lines = text.splitlines()
    keywords = ['razem', 'suma', 'łącznie', 'do zapłaty']

    for line in lines:
        # Uproszczenie: usuń wielokrotne spacje i zamień przecinki na kropki
        raw_line = line.lower()
        if any(kw in raw_line for kw in keywords):
            clean_line = raw_line.replace(",", ".")
            clean_line = re.sub(r"\s+", "", clean_line)  # usunięcie spacji z liczb

            # Szukamy trzech floatów (np. 1169.70 269.03 1438.73)
            match = re.findall(r"\d+\.\d{2}", clean_line)
            if len(match) >= 3:
                netto, vat, brutto = match[:3]
                return {
                    "netto": float(netto),
                    "vat": float(vat),
                    "brutto": float(brutto)
                }

    return {
        "netto": None,
        "vat": None,
        "brutto": None
    }
