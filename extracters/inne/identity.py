import re

# Nasza własna firma (zawsze nabywca na tych fakturach) — linie ją
# zawierające są pomijane przy szukaniu nazwy kontrahenta (sprzedawcy).
OWN_COMPANY_MARKERS = ("sopocki", "świątkowski", "swiatkowski")

# Faktury spoza KSeF nie mają etykiety "Sprzedawca" — nazwę kontrahenta
# rozpoznajemy po sufiksie formy prawnej w nazwie (działa dla zagranicznych
# i polskich dostawców/agencji OTA: GmbH, B.V., LLC, S.A., Sp. z o.o., ...).
SUFFIXES = ["GmbH", "B.V.", "BV", "LLC", "S.A.", "SA", "Sp. z o.o.", "Ltd", "Inc"]

# Niektóre OTA fakturują przez formalną spółkę-córkę, a nie markę, pod którą
# faktycznie znamy kontrahenta (np. Expedia Group rozlicza się jako
# "Travelscape LLC"). Sprawdzane przed wykrywaniem po sufiksie formy prawnej.
BRAND_OVERRIDES = {
    "expedia": "Expedia",
}

# Niektóre faktury mają dalsze strony (tabele rezerwacji/transakcji), których
# OCR regularnie wychodzi nieczytelny, a wszystkie potrzebne pola są i tak na
# stronie 1 (np. HRS — tabela klientów w układzie, który myli Tesseract).
# Dla takich firm główny skrypt OCR-uje tylko stronę 1.
SINGLE_PAGE_ONLY_MARKERS = ("hrs gmbh",)


def is_single_page_invoice(first_page_text: str) -> bool:
    low = first_page_text.lower()
    return any(marker in low for marker in SINGLE_PAGE_ONLY_MARKERS)


def extract_seller_name(text: str) -> str:
    low_text = text.lower()
    for keyword, brand in BRAND_OVERRIDES.items():
        if keyword in low_text:
            return brand

    lines = text.splitlines()
    for line in lines[:80]:
        low = line.lower()
        if any(marker in low for marker in OWN_COMPANY_MARKERS):
            continue
        best = None
        for suffix in SUFFIXES:
            # Wymagamy granic "nie-alfanumerycznych" wokół sufiksu, żeby np.
            # "Inc" nie złapało się w środku słowa "including".
            pattern = r"(?<![A-Za-z0-9])" + re.escape(suffix) + r"(?![A-Za-z0-9])"
            match = re.search(pattern, line, re.IGNORECASE)
            if match and (best is None or match.end() < best.end()):
                best = match
        if best:
            candidate = _extract_name_before_suffix(line, best)
            if candidate:
                return candidate
    return "brak"


def _extract_name_before_suffix(line: str, suffix_match) -> str:
    """
    Zamiast brać cały fragment linii do końca sufiksu (co łapie całe zdanie,
    gdy nazwa firmy jest wpisana w środku dłuższego tekstu — np. niemiecki
    tekst prawny "... der Aurena GmbH."), cofamy się od sufiksu i bierzemy
    tylko kolejne słowa zaczynające się wielką literą (nazwa własna), aż
    trafimy na pierwsze słowo pisane z małej litery.
    """
    prefix_words = re.findall(r"\S+", line[: suffix_match.start()])
    name_words = []
    for word in reversed(prefix_words):
        if re.match(r"^[A-ZÀ-ÖØ-Þ0-9]", word):
            name_words.insert(0, word)
        else:
            break
    if not name_words:
        # Sam sufiks, bez żadnego słowa przed nim — zwykle szum OCR z
        # logo/nagłówka (np. "Sa" jako samodzielny fragment), nie prawdziwa
        # nazwa firmy. Zgłaszamy "nie znaleziono", żeby wołający szukał dalej.
        return None
    name_words.append(line[suffix_match.start(): suffix_match.end()])
    candidate = " ".join(name_words).strip()
    # Odcina resztki cudzysłowu/dwukropka, gdy nazwa była cytowana (np.
    # 'Credit to: "Travelscape LLC').
    candidate = re.split(r'[:"]', candidate)[-1].strip()
    return candidate
