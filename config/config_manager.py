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
    """Zwraca dane o firmie. Jeśli brak w bazie, bierze default_dept z settings."""
    # 1. Sprawdź Aliasy
    for canonical_name, data in patterns.items():
        if raw_firm in data.get("aliases", []):
            return canonical_name, data.get("dzial", "")

    # 2. Sprawdź czy firma już jest w patterns bezpośrednio
    if raw_firm in patterns:
        return raw_firm, patterns[raw_firm].get("dzial", "")

    # 3. Jeśli firma jest zupełnie nowa, pobierz default_dept z settings.json
    settings = load_settings()
    fallback = settings.get("default_dept", "Do przypisania")
    return raw_firm, fallback

def update_knowledge_base(scanned_firm, final_firm, final_dept):
    """Dodaje nową wiedzę o firmie, jej dziale i aliasie sczytanym przez OCR."""
    patterns = load_patterns()
    if final_firm not in patterns:
        patterns[final_firm] = {"dzial": final_dept, "aliases": []}
    
    if scanned_firm != final_firm and scanned_firm not in patterns[final_firm]["aliases"]:
        patterns[final_firm]["aliases"].append(scanned_firm)
    
    patterns[final_firm]["dzial"] = final_dept
    save_patterns(patterns)