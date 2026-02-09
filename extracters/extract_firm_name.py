import re

def extract_firm_name(text: str) -> str:
    lines = text.splitlines()
    
    # Lista słów, które oznaczają sekcję wystawcy
    seller_keywords = ["sprzedawca", "wystawca", "dostawca"]
    
    found_name = "dokument"

    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in seller_keywords):
            # Szukamy w 3 kolejnych liniach, bo czasem "Sprzedawca:" jest w osobnej linii niż nazwa
            for next_line in lines[i+1:i+4]:
                clean_line = next_line.strip()
                if clean_line and len(clean_line) > 3:
                    # Czyścimy znaki specjalne, zostawiamy litery, cyfry i podstawowe znaki
                    name = "".join(c for c in clean_line if c.isalnum() or c in (' ', '_', '-')).strip()
                    
                    # Poprawiamy typowe błędy OCR dla "Sp. z o.o."
                    name = re.sub(r'\b0\.0\b', 'o.o.', name, flags=re.IGNORECASE)
                    name = re.sub(r'\b00\b', 'oo', name, flags=re.IGNORECASE)
                    name = re.sub(r'\bsp z oo\b', 'Sp. z o.o.', name, flags=re.IGNORECASE)
                    
                    found_name = name
                    break
            if found_name != "dokument":
                break

    # Jeśli nazwa jest zbyt długa (częsty błąd OCR, który łapie adres), ucinamy ją
    if len(found_name) > 60:
        found_name = found_name[:60].strip()

    return found_name