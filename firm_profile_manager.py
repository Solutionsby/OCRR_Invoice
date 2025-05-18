import json
from pathlib import Path

PROFILE_FILE = Path(__file__).parent / "firm_profiles.json"



def load_firm_profiles():
    if PROFILE_FILE.exists():
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}


def save_firm_profiles(profiles):
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def firm_to_id(name: str) -> str:
    """Zamienia nazwę firmy na bezpieczny identyfikator (do JSON)."""
    return name.lower().replace(" ", "_").replace(".", "").replace(",", "").strip()


def get_profile_for_firm(firm_name: str) -> dict | None:
    profiles = load_firm_profiles()
    firm_id = firm_to_id(firm_name)
    return profiles.get(firm_id)

def get_all_profiles() -> dict:
    return load_firm_profiles()

def match_firm_by_alias(name: str) -> str | None:
    aliases = get_all_aliases()  # słownik: alias -> nazwa_firmy
    normalized = name.lower().strip()
    return aliases.get(normalized)

def add_alias_to_profile(firm_name: str, alias: str):
    profiles = load_firm_profiles()
    firm_id = firm_to_id(firm_name)

    data = profiles.get(firm_id, {})
    aliases = data.get("aliases", [])
    normalized_alias = alias.lower().strip()
    if normalized_alias not in [a.lower().strip() for a in aliases]:
        aliases.append(alias)
        data["aliases"] = aliases
        profiles[firm_id] = data
        save_firm_profiles(profiles)
        print(f"🔗 Dodano alias: '{alias}' → '{firm_name}'")





def update_profile(firm_name: str, updates: dict):
    profiles = load_firm_profiles()
    firm_id = firm_to_id(firm_name)

    if firm_id not in profiles:
        profiles[firm_id] = {}

    profiles[firm_id].update(updates)
    save_firm_profiles(profiles)
    print(f"💾 Zaktualizowano profil dla firmy {firm_id}: {updates}")

    print(f"Zaktualizowano profil firmy: {firm_id}")

def get_all_aliases() -> dict:
    """Zwraca słownik: alias (znormalizowany) -> nazwa_firmy (oryginalna)"""
    profiles = load_firm_profiles()
    aliases = {}
    for firm_id, data in profiles.items():
        firm_name = data.get("name", firm_id.replace("_", " ").title())
        for alias in data.get("aliases", []):
            normalized = alias.lower().strip()
            aliases[normalized] = firm_name
        # Dodaj też główną nazwę jako alias do siebie
        normalized_main = firm_name.lower().strip()
        aliases[normalized_main] = firm_name
    return aliases
