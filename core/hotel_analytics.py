from __future__ import annotations

import re

from utils import mongo_manager as mongo

# Nazwy pozycji sprzedaży wpisywane są w systemie hotelowym (recepcja/POS) —
# ta sama pozycja trafia pod kilkoma wariantami: literówka w interpunkcji
# ("Parking Doba." vs "Parking Doba"), albo dopisek w nawiasie ze statusem/
# referencją konkretnej transakcji ("Usługa zakwaterowania (płatność
# częściowa)", "ZAKWATEROWANIE I WYŻYWIENIE (ZAL 4/F/06/2026 z dnia...)") —
# to nie różne produkty, tylko ta sama pozycja z inną adnotacją. "Zadatek..."
# ma dodatkowo osadzone konkretne daty pobytu w treści (nie w nawiasie) —
# każdy taki wpis jest z definicji unikalny per rezerwacja, więc grupujemy
# wszystkie pod jedną etykietę "Zadatek" zamiast dziesiątek osobnych "pozycji".
_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def _normalize_product_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return "(brak nazwy)"
    if n.lower().startswith("zadatek"):
        return "Zadatek"
    n = _PAREN_SUFFIX.sub("", n).strip()
    n = n.rstrip(".").strip()
    return n or "(brak nazwy)"


# Ręczne przypisanie znormalizowanej nazwy pozycji do kategorii (na życzenie
# użytkownika, żeby móc odfiltrować np. wszystko związane z rowerem jedną
# etykietą zamiast czterech osobnych pozycji). Domyślna kategoria dla
# wszystkiego nieprzypisanego to "Inne" — rozszerzać przez dopisanie kolejnych
# wpisów tutaj, bez zmian gdzie indziej.
_CATEGORY_RULES: dict[str, str] = {
    "Rower 24\"/20\"": "Rowery",
    "Rower 28\"/26\"": "Rowery",
    "Rower z fotelikiem": "Rowery",
    "Wypożyczenie roweru": "Rowery",
    "Kask": "Rowery",
    "Doba Parking": "Parking",
    "Parking 7 dni": "Parking",
    "Parking Doba": "Parking",
    "Parking Kamper": "Parking",
    "Parking godzina": "Parking",
    "Parking na tyłach obiektu": "Parking",
    "Parking przy głównym wejściu": "Parking",
    "Usługa zakwaterowania": "Noclegi",
    "ZAKWATEROWANIE I WYŻYWIENIE": "Noclegi",
    "Uzdrowiskowa": "Noclegi",
    "Zadatek": "Noclegi",
    "Biżuteria": "Sklepik",
    "Pocztówka": "Sklepik",
    "Pocztówka Hotel": "Sklepik",
    "Pocztówka Hotel z wysyłką": "Sklepik",
    "Kubek Sopocki Zdrój": "Sklepik",
    "Łyżka do butów": "Sklepik",
    "Płaszcz przeciwdeszczowy": "Sklepik",
    "Obiad": "Wyżywienie",
    "Śniadanie Hotel": "Wyżywienie",
    "Śniadanie na wynos": "Wyżywienie",
    "Doba Pupil": "Usługi dodatkowe",
    "Pupil": "Usługi dodatkowe",
    "Klucz": "Usługi dodatkowe",
    "Wynajem leżaka": "Usługi dodatkowe",
    "Usługa odprowadzenia nieczystości": "Usługi dodatkowe",
    "usluga dodatkowa": "Usługi dodatkowe",
    "przedłużenie doba": "Usługi dodatkowe",
    "dodatkowa osoba": "Usługi dodatkowe",
    "Heets Marlboro Amber": "Papierosy",
    "Heets Marlboro Russet": "Papierosy",
    "Neo Sticks Arctic Blue Click": "Papierosy",
    "Neo Sticks ICE Click": "Papierosy",
    "Neo Sticks Syellow Summer Click": "Papierosy",
}
_DEFAULT_CATEGORY = "Inne"


def _categorize(normalized_name: str) -> str:
    return _CATEGORY_RULES.get(normalized_name, _DEFAULT_CATEGORY)


def get_sales_trend(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Miesięczny trend sprzedaży (wszystkie pozycje razem) — zakładka
    Hotel, wykres trendu."""
    points = mongo.get_incomes_trend(year_from, month_from, year_to, month_to)
    return {
        "points": points,
        "total_brutto": round(sum(p["brutto"] for p in points), 2),
        "total_netto": round(sum(p["netto"] for p in points), 2),
        "total_count": sum(p["count"] for p in points),
    }


def get_sales_breakdown(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Suma brutto per znormalizowana pozycja sprzedaży (co się sprzedawało)
    w wybranym oknie, posortowana malejąco, plus zestawienie per kategoria
    (patrz _CATEGORY_RULES) do szybkiego filtrowania."""
    raw = mongo.get_incomes_raw(year_from, month_from, year_to, month_to)

    groups: dict[str, dict] = {}
    for r in raw:
        key = _normalize_product_name(r["nazwa"])
        g = groups.setdefault(key, {"nazwa": key, "kategoria": _categorize(key), "brutto": 0.0, "count": 0})
        g["brutto"] += r["brutto"]
        g["count"] += 1

    items = sorted(groups.values(), key=lambda i: i["brutto"], reverse=True)
    total = round(sum(i["brutto"] for i in items), 2)
    for i in items:
        i["brutto"] = round(i["brutto"], 2)
        i["pct"] = round(i["brutto"] / total * 100, 1) if total else 0.0

    cat_groups: dict[str, dict] = {}
    for i in items:
        c = cat_groups.setdefault(i["kategoria"], {"kategoria": i["kategoria"], "brutto": 0.0, "count": 0})
        c["brutto"] += i["brutto"]
        c["count"] += i["count"]
    categories = sorted(cat_groups.values(), key=lambda c: c["brutto"], reverse=True)
    for c in categories:
        c["brutto"] = round(c["brutto"], 2)
        c["pct"] = round(c["brutto"] / total * 100, 1) if total else 0.0

    return {"items": items, "total_brutto": total, "categories": categories}


def get_payment_methods(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Rozbicie sprzedaży wg formy płatności (Gotówka/Przelew/Karta...) per
    miesiąc, plus zestawienie sumaryczne za cały wybrany zakres — zakładka
    Płatności."""
    by_month_method = mongo.get_incomes_by_payment_method(year_from, month_from, year_to, month_to)

    months = []
    totals: dict[str, dict] = {}
    for (year, month), methods in sorted(by_month_method.items()):
        month_entry = {"year": year, "month": month, "methods": {}, "total_brutto": 0.0, "total_count": 0}
        for method, vals in methods.items():
            month_entry["methods"][method] = {"brutto": round(vals["brutto"], 2), "count": vals["count"]}
            month_entry["total_brutto"] += vals["brutto"]
            month_entry["total_count"] += vals["count"]
            t = totals.setdefault(method, {"brutto": 0.0, "count": 0})
            t["brutto"] += vals["brutto"]
            t["count"] += vals["count"]
        month_entry["total_brutto"] = round(month_entry["total_brutto"], 2)
        months.append(month_entry)

    total_brutto = round(sum(t["brutto"] for t in totals.values()), 2)
    totals_list = sorted(
        (
            {
                "method": method,
                "brutto": round(vals["brutto"], 2),
                "count": vals["count"],
                "pct": round(vals["brutto"] / total_brutto * 100, 1) if total_brutto else 0.0,
            }
            for method, vals in totals.items()
        ),
        key=lambda t: t["brutto"], reverse=True,
    )
    return {"months": months, "totals": totals_list, "total_brutto": total_brutto}


def get_records(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Wszystkie surowe rekordy w oknie (bez deduplikacji) do ręcznego
    przeglądu — zakładka Rekordy. `is_duplicate` liczone tą samą regułą co
    wykres trendu (mongo._dedupe_incomes), żeby podpowiedzieć które wiersze
    są kandydatami do skasowania, ale finalną decyzję zostawiamy
    użytkownikowi."""
    records = mongo.get_incomes_records(year_from, month_from, year_to, month_to)
    return {
        "records": records,
        "total_count": len(records),
        "duplicate_count": sum(1 for r in records if r["is_duplicate"]),
    }


def delete_record(record_id: str) -> bool:
    return mongo.delete_income_record(record_id)
