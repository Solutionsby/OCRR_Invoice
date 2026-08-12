import json
from pathlib import Path

# Prosta mapa firma -> {dzial, kategoria} dla faktur spoza KSeF. W
# odróżnieniu od json/knowledge_base.json (historia wielu kategorii na
# firmę, uczona przez KSeF-owy flow) tutaj potrzebna jest jedna kanoniczna
# wartość na pole, bo Dzial/Kategoria to kolumny wymagane przy zapisie do
# FAKTURY_KOSZTOWE — stąd osobny, prostszy plik.
KB_PATH = Path("json/dzial_kategoria.json")


def load_map() -> dict:
    if not KB_PATH.exists():
        return {}
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_map(data: dict):
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_dzial_kategoria(firm_name: str):
    """Zwraca (dzial, kategoria) jeśli firma jest znana, inaczej (None, None)."""
    entry = load_map().get(firm_name)
    if entry:
        return entry.get("dzial", ""), entry.get("kategoria", "")
    return None, None


def update_dzial_kategoria(firm_name: str, dzial: str, kategoria: str):
    if not firm_name:
        return
    data = load_map()
    data[firm_name] = {"dzial": dzial, "kategoria": kategoria}
    save_map(data)
