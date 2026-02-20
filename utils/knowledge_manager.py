import json
from pathlib import Path

KB_PATH = Path("json/knowledge_base.json")

def load_kb():
    if not KB_PATH.exists():
        # Inicjalizacja domyślna
        return {"dostepne_dzialy": [], "historia_firm": {}}
    with open(KB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_kb(data):
    with open(KB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_suggestions(firm_name):
    kb = load_kb()
    data = kb["historia_firm"].get(firm_name, {})
    
    # Zwraca: Sugerowany Dział, Listę znanych kategorii dla tej firmy, Wszystkie działy
    return (
        data.get("dzial", []), 
        data.get("kategorie", []), 
        kb["dostepne_dzialy"]
    )

def update_firm_knowledge(firm_name, dzial, kategoria):
    kb = load_kb()
    
    # Dodaj nowy dział do listy, jeśli go nie ma
    if dzial not in kb["dostepne_dzialy"]:
        kb["dostepne_dzialy"].append(dzial)
    
    # Aktualizuj dane firmy
    if firm_name not in kb["historia_firm"]:
        kb["historia_firm"][firm_name] = {"dzial": dzial, "kategorie": []}
    
    kb["historia_firm"][firm_name]["dzial"] = dzial
    
    if kategoria and kategoria not in kb["historia_firm"][firm_name]["kategorie"]:
        kb["historia_firm"][firm_name]["kategorie"].append(kategoria)
        
    save_kb(kb)