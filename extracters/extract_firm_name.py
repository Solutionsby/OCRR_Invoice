import re

def extract_firm_name(text: str, left_column_text: str = None) -> str:
    """
    Odczytuje nazwę sprzedawcy (kontrahenta kosztowego) z tekstu OCR.

    Część wizualizacji KSeF ma układ dwukolumnowy Sprzedawca/Nabywca, przez co
    zwykły odczyt całej strony potrafi pomieszać obie kolumny (np. "Nazwa: X
    Nazwa: Y" w jednej linii, albo w skrajnych przypadkach linie "Nazwa:" obu
    kontrahentów w złej kolejności, daleko od swoich sekcji). Jeśli wywołujący
    dostarczy `left_column_text` (OCR samej lewej połowy strony — tam zawsze
    jest kolumna Sprzedawcy), szukamy nazwy najpierw tam, bo nigdy nie styka
    się z kolumną Nabywcy.
    """
    if left_column_text:
        name = _find_seller_name(left_column_text)
        if name != "dokument":
            return _finalize(name)

    name = _find_seller_name(text)
    return _finalize(name)


def _find_seller_name(text: str) -> str:
    lines = text.splitlines()

    # Lista słów, które oznaczają sekcję wystawcy
    seller_keywords = ["sprzedawca", "wystawca", "dostawca"]

    found_name = "dokument"

    for i, line in enumerate(lines):
        lower_line = line.lower()
        if any(kw in lower_line for kw in seller_keywords):

            # Wariant dwukolumnowy w jednej linii (np. "Sprzedawca Nabywca"),
            # gdzie wartości też lądują razem: "Nazwa: X Nazwa: Y".
            if "nabywca" in lower_line:
                for next_line in lines[i+1:i+8]:
                    merged_match = re.search(r"nazwa\s*:\s*(.+?)\s+nazwa\s*:", next_line, re.IGNORECASE)
                    if merged_match:
                        found_name = _clean_name(merged_match.group(1))
                        break
            else:
                # KSeF: pod nagłówkiem sekcji jest wprost etykieta "Nazwa: ..."
                # (poprzedzona np. linią NIP), więc szukamy jej w kilku kolejnych
                # liniach, zatrzymując się na sekcji Nabywcy.
                for next_line in lines[i+1:i+15]:
                    if "nabywca" in next_line.lower():
                        break
                    label_match = re.match(r"\s*nazwa\s*:\s*(.+)", next_line, re.IGNORECASE)
                    if label_match:
                        found_name = _clean_name(label_match.group(1))
                        break

            # Fallback dla skanów spoza KSeF, gdzie nazwa firmy jest po prostu
            # pierwszą sensowną linią pod nagłówkiem sekcji.
            if found_name == "dokument":
                for next_line in lines[i+1:i+4]:
                    clean_line = next_line.strip()
                    if clean_line and len(clean_line) > 3:
                        found_name = _clean_name(clean_line)
                        break

            if found_name != "dokument":
                break

    return found_name


def _clean_name(raw: str) -> str:
    # Czyścimy znaki specjalne, zostawiamy litery, cyfry i podstawowe znaki
    name = "".join(c for c in raw.strip() if c.isalnum() or c in (' ', '_', '-'))

    # Poprawiamy typowe błędy OCR dla "Sp. z o.o."
    name = re.sub(r'\b0\.0\b', 'o.o.', name, flags=re.IGNORECASE)
    name = re.sub(r'\b00\b', 'oo', name, flags=re.IGNORECASE)
    name = re.sub(r'\bsp z oo\b', 'Sp. z o.o.', name, flags=re.IGNORECASE)

    return name.strip()


def _finalize(name: str) -> str:
    # Jeśli nazwa jest zbyt długa (częsty błąd OCR, który łapie adres), ucinamy ją
    if len(name) > 60:
        name = name[:60].strip()
    return name
