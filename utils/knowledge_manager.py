import json
from pathlib import Path

KB_PATH = Path("json/knowledge_base.json")

def load_kb():
    if not KB_PATH.exists():
        # Inicjalizacja domyślna
        return {"historia_firm": {}}
    with open(KB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_kb(data):
    with open(KB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def update_firm_knowledge(firm_name, kategoria):
    kb = load_kb()

    if firm_name not in kb["historia_firm"]:
        kb["historia_firm"][firm_name] = {"kategorie": []}

    if kategoria and kategoria not in kb["historia_firm"][firm_name].get("kategorie", []):
        kb["historia_firm"][firm_name].setdefault("kategorie", []).append(kategoria)

    save_kb(kb)
