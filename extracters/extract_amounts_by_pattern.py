import re
import json
from pathlib import Path

PATTERNS_FILE = Path("patterns.json")

def extract_invoice_amounts(text: str, firm_name: str = None) -> dict:
    # Czyścimy tekst do jednej linii dla łatwiejszego regexu
    text_clean = re.sub(r"\s+", " ", text)
    amounts = {"netto": None, "vat": None, "brutto": None}
    
    if not firm_name or not PATTERNS_FILE.exists():
        return amounts

    try:
        with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
            all_patterns = json.load(f)
            # Dopasowanie firmy (case-insensitive)
            pattern = next((v for k, v in all_patterns.items() if k.lower().strip() == firm_name.lower().strip()), None)
            
            if pattern:
                for key in ["netto", "vat", "brutto"]:
                    anchor = pattern.get(f"{key}_anchor")
                    if anchor == "0":
                        amounts[key] = 0.0
                    elif anchor:
                        # Szukamy kwoty po kotwicy
                        match = re.search(f"{re.escape(anchor)}[:\s]*([\d\s,.]+\d{{2}})", text_clean, re.IGNORECASE)
                        if match:
                            val = match.group(1).replace(" ", "").replace(",", ".")
                            amounts[key] = float(val)
    except:
        pass

    return amounts