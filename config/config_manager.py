import json
from pathlib import Path


SETTINGS_FILE = Path("settings.json")
PATTERNS_FILE = Path("patterns.json")

def load_settings():
    """Wczytuje listę działów tylko i wyłącznie z settings.json."""
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_patterns():
    """Wczytuje bazę firm/aliasów. Jeśli plik nie istnieje, zwraca pusty słownik."""
    if not PATTERNS_FILE.exists():
        return {}
    with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_patterns(patterns):
    """Zapisuje aktualną wiedzę o firmach/aliasach do patterns.json."""
    with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=4, ensure_ascii=False)

def get_firm_data(raw_firm, patterns):
    """Zwraca kanoniczną nazwę firmy na podstawie zapisanych aliasów."""
    for canonical_name, data in patterns.items():
        if raw_firm in data.get("aliases", []):
            return canonical_name
    return raw_firm

def update_knowledge_base(scanned_firm, final_firm):
    """Dodaje nowy alias firmy sczytany przez OCR do patterns.json."""
    patterns = load_patterns()
    if final_firm not in patterns:
        patterns[final_firm] = {"aliases": []}

    if scanned_firm != final_firm and scanned_firm not in patterns[final_firm]["aliases"]:
        patterns[final_firm]["aliases"].append(scanned_firm)

    save_patterns(patterns)