import re

# Kolejność ma znaczenie: etykiety wcześniej na liście są sprawdzane
# pierwsze, niezależnie od tego, gdzie w tekście się znajdują. "R.Nr." jest
# na końcu — to skrót podatny na rozjazd OCR w dwukolumnowym nagłówku
# (Aurena: kolumna etykiet "R.Nr./Ort/Datum/..." osobno od kolumny wartości),
# więc jego najbliższy token w tekście czasem wcale nie jest numerem.
# "Rechnungsnummer" (pełne słowo, zawsze w osobnym, nierozjechanym zdaniu:
# "Bei Uberweisungen ... Rechnungsnummer ... an: <numer>") jest dużo
# pewniejsze i sprawdzane wcześniej.
LABELS = [
    r"numer\s+faktury",
    r"numer\s+rachunku",
    r"invoice\s*(?:number|no\.?|#)",
    r"nr\s*faktury",
    r"faktura\s*nr",
    r"rachunek\s*nr",
    r"rechnungsnummer",
    r"r\.?\s*nr\.?",
]

# Numer nie musi być pierwszym tokenem po etykiecie (np. "Rechnungsnummer
# als Verwendungszweck an: 1-A-17348-127" ma dwa słowa wypełniające między
# etykietą a numerem) — szukamy więc pierwszego tokenu z cyfrą w oknie za
# etykietą, a nie tylko bezpośrednio przylegającego tokenu.
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]*")
_WINDOW = 60


def extract_invoice_number(text: str) -> str:
    for label in LABELS:
        label_re = re.compile(label, re.IGNORECASE)
        for label_match in label_re.finditer(text):
            window = text[label_match.end(): label_match.end() + _WINDOW]
            for token_match in _TOKEN_RE.finditer(window):
                candidate = token_match.group(0)
                # Numer faktury zawiera zawsze przynajmniej jedną cyfrę —
                # odrzuca to np. "Ort"/"UID"/"als" złapane po rozjechanej
                # albo wielosłowowej etykiecie.
                if any(ch.isdigit() for ch in candidate):
                    return candidate
    return "brak-nr"
