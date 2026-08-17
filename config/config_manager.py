import json
from pathlib import Path


# Wewnątrz json/ (nie w katalogu głównym) celowo — json/ jest realnym,
# śledzonym przez git katalogiem (ma już knowledge_base.json/dzial_kategoria.json),
# więc bind mount w Dockerze zawsze montuje istniejący katalog. settings.json
# i patterns.json są w .gitignore (dane per-instalacja) — na świeżym
# checkoucie repo (nowy komputer) fizycznie nie istnieją, a Docker przy
# montowaniu POJEDYNCZEGO brakującego pliku cicho tworzy zamiast niego pusty
# katalog na hoście, co potem wywala open() z IsADirectoryError. Montując
# tylko katalog json/ i tworząc te pliki od środka (przez Pythona, gdy
# brakuje), ten problem znika całkowicie.
CONFIG_DIR = Path("json")
SETTINGS_FILE = CONFIG_DIR / "settings.json"
PATTERNS_FILE = CONFIG_DIR / "patterns.json"

DEFAULT_SETTINGS = {
    "email_config": {
        "smtp_port": 465,
        "days_window": 7,
        "recipients": [],
    }
}

def load_settings():
    """
    Wczytuje settings.json. Jeśli jeszcze nie istnieje (świeży checkout na
    nowym komputerze), tworzy go z domyślną zawartością zamiast wywalać
    błędem — inaczej cała aplikacja (CLI i API) nie startuje w ogóle.
    """
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(settings):
    """Zapisuje settings.json (np. politykę mailera edytowaną z przeglądarki)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

def load_patterns():
    """Wczytuje bazę firm/aliasów. Jeśli plik nie istnieje, zwraca pusty słownik."""
    if not PATTERNS_FILE.exists():
        return {}
    with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_patterns(patterns):
    """Zapisuje aktualną wiedzę o firmach/aliasach do patterns.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
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
