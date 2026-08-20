from __future__ import annotations

import statistics
from datetime import date

from utils import database_manager as db

# KATEGORIA/PODKATEGORIA wpisywane są ręcznie przy księgowaniu faktur "inne" —
# ta sama kategoria często trafia do bazy pod kilkoma pisowniami (wielkość
# liter już scala SQL Server, collation Polish_CI_AS jest Case Insensitive;
# to, czego SQL nie łapie, to BRAK polskich znaków, np. "Częsci"/"Cześci"/
# "Czesci"/"Części" — 4 warianty tego samego). Mapa usuwa tylko ogonki/kreski,
# nie liczbę/rodzaj gramatyczny — "Kurier" i "Kurier, transporty" zostają
# osobno, bo to naprawdę różny tekst, nie literówka.
_PL_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def _normalize_label(s: str) -> str:
    return " ".join(s.translate(_PL_MAP).lower().split())


def _merge_variants(items: list, label_field: str) -> list:
    """Grupuje pozycje po znormalizowanej etykiecie, sumuje brutto/count, i
    jako wyświetlaną etykietę wybiera wariant z najwyższą sumą brutto
    (zwykle najczęściej/najpoprawniej zapisany). `_raw_labels` niesie
    wszystkie surowe warianty grupy — potrzebne przy drill-down
    kategoria→podkategoria, żeby dociągnąć podkategorie ze WSZYSTKICH
    wariantów, nie tylko z wybranej etykiety (patrz get_podkategoria_breakdown
    poniżej i db.get_podkategoria_breakdown)."""
    groups: dict[str, dict] = {}
    for it in items:
        key = _normalize_label(it[label_field])
        g = groups.setdefault(key, {"variants": [], "brutto": 0.0, "count": 0})
        g["variants"].append(it)
        g["brutto"] += it["brutto"]
        g["count"] += it["count"]

    merged = []
    for g in groups.values():
        canonical = max(g["variants"], key=lambda v: v["brutto"])
        merged.append({
            label_field: canonical[label_field],
            "brutto": round(g["brutto"], 2),
            "count": g["count"],
            "_raw_labels": [v[label_field] for v in g["variants"]],
        })
    merged.sort(key=lambda i: i["brutto"], reverse=True)
    return merged


def get_spend_trend(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    points = db.get_spend_trend(year_from, month_from, year_to, month_to)
    return {
        "points": points,
        "total_netto": round(sum(p["netto"] for p in points), 2),
        "total_vat": round(sum(p["vat"] for p in points), 2),
        "total_brutto": round(sum(p["brutto"] for p in points), 2),
        "total_count": sum(p["count"] for p in points),
    }


def get_top_kontrahenci(year_from: int, month_from: int, year_to: int, month_to: int,
                         limit: int = 15, dzial: str | None = None) -> dict:
    items, total_brutto = db.get_top_kontrahenci(year_from, month_from, year_to, month_to, limit, dzial)
    return {"items": items, "total_brutto": total_brutto}


def get_dzial_trend(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Płaskie wiersze (rok, miesiąc, dział, brutto) przestawione w serie po
    dziale — wygodniejsze dla frontendu budującego wielolinowy wykres niż
    ręczne przestawianie płaskiej listy w JS."""
    rows = db.get_dzial_trend(year_from, month_from, year_to, month_to)

    months = sorted({(r["year"], r["month"]) for r in rows})
    by_dzial: dict[str, dict] = {}
    for r in rows:
        entry = by_dzial.setdefault(r["dzial"], {})
        entry[(r["year"], r["month"])] = r["brutto"]

    series = [
        {
            "dzial": dzial,
            "values": [by_dzial[dzial].get(m, 0.0) for m in months],
            "total": round(sum(by_dzial[dzial].values()), 2),
        }
        for dzial in by_dzial
    ]
    series.sort(key=lambda s: s["total"], reverse=True)

    return {
        "months": [{"year": y, "month": m} for y, m in months],
        "series": series,
    }


def get_kategoria_breakdown(year_from: int, month_from: int, year_to: int, month_to: int, dzial: str | None = None) -> dict:
    items = _merge_variants(db.get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial), "kategoria")
    total_brutto = round(sum(i["brutto"] for i in items), 2)
    for i in items:
        i["pct"] = round(i["brutto"] / total_brutto * 100, 1) if total_brutto else 0.0
        del i["_raw_labels"]
    return {"items": items, "total_brutto": total_brutto}


def _contiguous_history(points: list) -> list:
    """Najdłuższy ciągły ogon historii (bez przerw miesiąc-do-miesiąca),
    licząc od najnowszego punktu wstecz do pierwszej luki. Chroni prognozę
    przed pojedynczymi, odległymi wpisami (np. 1 faktura z grudnia 2018 przy
    realnej, ciągłej historii dopiero od 2024) — bez tego zniekształcałyby
    wskaźnik sezonowości, nie odzwierciedlając bieżącej działalności."""
    if not points:
        return []
    pts = sorted(points, key=lambda p: (p["year"], p["month"]))
    result = [pts[-1]]
    for p in reversed(pts[:-1]):
        last = result[-1]
        prev_idx = last["year"] * 12 + (last["month"] - 1) - 1
        if p["year"] * 12 + (p["month"] - 1) == prev_idx:
            result.append(p)
        else:
            break
    return list(reversed(result))


def get_spend_forecast(months_ahead: int = 3) -> dict:
    """
    Prosty, przejrzysty baseline — NIE model ML. Dane są bardzo nierówne
    (pojedyncze duże faktury potrafią zdominować miesiąc), dlatego wszędzie
    mediana zamiast średniej — dużo mniej wrażliwa na takie skoki:

    1. Bierzemy najdłuższy ciągły ogon historii miesięcznej (patrz
       _contiguous_history) — z pojedynczymi lukami dawnych lat baseline
       byłby myslący.
    2. Wskaźnik sezonowości miesiąca kalendarzowego = mediana brutto tego
       miesiąca w historii / mediana brutto całej historii (ile dany miesiąc
       kalendarzowy typowo odstaje od przeciętnego).
    3. Poziom = mediana z ostatnich (do 12) miesięcy PO odsezonowaniu — czyli
       bieżący "typowy" poziom kosztów, oczyszczony z sezonowych wahań.
    4. Prognoza kolejnych miesięcy = poziom × wskaźnik sezonowości tego
       miesiąca kalendarzowego.
    """
    today = date.today()
    all_points = db.get_spend_trend(2000, 1, today.year, today.month)
    history = _contiguous_history(all_points)

    if len(history) < 3:
        return {
            "history": history, "forecast": [], "seasonal_index": {},
            "history_months": len(history), "level": 0.0,
        }

    # Bieżący miesiąc jest z definicji niekompletny (wciąż trwa) — zostaje
    # widoczny w zwracanej historii (przejrzystość dla użytkownika), ale NIE
    # wchodzi do statystyk (poziom, wskaźnik sezonowości) i jest prognozowany
    # od nowa jako pierwszy punkt prognozy, zamiast traktować niepełne dane
    # jak typowy wynik tego miesiąca.
    stats_history = history
    last_idx = history[-1]["year"] * 12 + (history[-1]["month"] - 1)
    if history[-1]["year"] == today.year and history[-1]["month"] == today.month and len(history) > 3:
        stats_history = history[:-1]
        last_idx -= 1

    overall_median = statistics.median(p["brutto"] for p in stats_history)

    by_month: dict[int, list] = {}
    for p in stats_history:
        by_month.setdefault(p["month"], []).append(p["brutto"])
    seasonal_index = {
        m: round(statistics.median(vals) / overall_median, 3) if overall_median else 1.0
        for m, vals in by_month.items()
    }

    window = stats_history[-12:]
    deseasonalized = [p["brutto"] / (seasonal_index.get(p["month"]) or 1.0) for p in window]
    level = statistics.median(deseasonalized) if deseasonalized else overall_median

    forecast = []
    for i in range(1, months_ahead + 1):
        idx = last_idx + i
        y, m = idx // 12, idx % 12 + 1
        forecast.append({"year": y, "month": m, "brutto": round(level * seasonal_index.get(m, 1.0), 2)})

    return {
        "history": history,
        "forecast": forecast,
        "seasonal_index": {str(m): seasonal_index.get(m, 1.0) for m in range(1, 13)},
        "history_months": len(history),
        "level": round(level, 2),
    }


def get_podkategoria_breakdown(year_from: int, month_from: int, year_to: int, month_to: int,
                                kategoria: str, dzial: str | None = None) -> dict:
    # `kategoria` to etykieta kanoniczna scalonej grupy (patrz get_kategoria_breakdown)
    # — trzeba odtworzyć, jakie surowe warianty KATEGORIA do niej należą, żeby
    # dociągnąć podkategorie ze wszystkich, nie tylko z jednego wariantu.
    raw_kategorie = db.get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial)
    target_key = _normalize_label(kategoria)
    variants = [i["kategoria"] for i in raw_kategorie if _normalize_label(i["kategoria"]) == target_key]
    if not variants:
        variants = [kategoria]

    items = _merge_variants(
        db.get_podkategoria_breakdown(year_from, month_from, year_to, month_to, variants, dzial),
        "podkategoria",
    )
    total_brutto = round(sum(i["brutto"] for i in items), 2)
    for i in items:
        i["pct"] = round(i["brutto"] / total_brutto * 100, 1) if total_brutto else 0.0
        del i["_raw_labels"]
    return {"items": items, "total_brutto": total_brutto}
