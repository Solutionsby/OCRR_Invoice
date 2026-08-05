import re

def extract_gross_amount(text: str) -> float:
    """
    Odczytuje ostateczną kwotę brutto do zapłaty z wizualizacji KSeF.
    Priorytet: "Do zapłaty:" (uwzględnia dodatkowe obciążenia, jeśli są np.
    opłaty sądowe doliczone do faktury notarialnej), w przeciwnym razie
    "Kwota należności ogółem:" (suma pozycji faktury).
    """
    for label in (r"Do zapłaty", r"Kwota należności ogółem"):
        match = re.search(rf"{label}\s*:\s*([\d\s]+[.,]\d{{1,2}})", text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                continue
    return 0.0
