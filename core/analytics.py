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


def get_spend_trend(year_from: int, month_from: int, year_to: int, month_to: int,
                     cykliczna: bool | None = None) -> dict:
    points = db.get_spend_trend(year_from, month_from, year_to, month_to, cykliczna)
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


def get_kategoria_breakdown(year_from: int, month_from: int, year_to: int, month_to: int,
                             dzial: str | None = None, cykliczna: bool | None = None) -> dict:
    items = _merge_variants(
        db.get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial, cykliczna), "kategoria",
    )
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


def _median_seasonal_forecast(points: list, value_field: str, months_ahead: int) -> dict:
    """
    Rdzeń prostego baseline'u (mediana + wskaźnik sezonowości) — NIE model ML.
    Dane są bardzo nierówne (pojedyncze duże faktury/transakcje potrafią
    zdominować miesiąc), dlatego wszędzie mediana zamiast średniej — dużo
    mniej wrażliwa na takie skoki. Reużywane przez get_spend_forecast (koszty
    całej firmy) i get_dochod_forecast (przychód/dochód pojedynczego działu) —
    `points` to lista {"year","month",value_field}, gdzie value_field nazywa
    klucz z wartością do prognozowania.

    1. Bierzemy najdłuższy ciągły ogon historii miesięcznej (patrz
       _contiguous_history) — z pojedynczymi lukami dawnych lat baseline
       byłby myslący.
    2. Wskaźnik sezonowości miesiąca kalendarzowego = mediana wartości tego
       miesiąca w historii / mediana wartości całej historii (ile dany
       miesiąc kalendarzowy typowo odstaje od przeciętnego).
    3. Poziom = mediana z ostatnich (do 12) miesięcy PO odsezonowaniu — czyli
       bieżący "typowy" poziom, oczyszczony z sezonowych wahań.
    4. Prognoza kolejnych miesięcy = poziom × wskaźnik sezonowości tego
       miesiąca kalendarzowego.
    """
    today = date.today()
    history = _contiguous_history(points)

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

    overall_median = statistics.median(p[value_field] for p in stats_history)

    by_month: dict[int, list] = {}
    for p in stats_history:
        by_month.setdefault(p["month"], []).append(p[value_field])
    seasonal_index = {
        m: round(statistics.median(vals) / overall_median, 3) if overall_median else 1.0
        for m, vals in by_month.items()
    }

    window = stats_history[-12:]
    deseasonalized = [p[value_field] / (seasonal_index.get(p["month"]) or 1.0) for p in window]
    level = statistics.median(deseasonalized) if deseasonalized else overall_median

    forecast = []
    for i in range(1, months_ahead + 1):
        idx = last_idx + i
        y, m = idx // 12, idx % 12 + 1
        forecast.append({"year": y, "month": m, "value": round(level * seasonal_index.get(m, 1.0), 2)})

    return {
        "history": history,
        "forecast": forecast,
        "seasonal_index": {str(m): seasonal_index.get(m, 1.0) for m in range(1, 13)},
        "history_months": len(history),
        "level": round(level, 2),
    }


def get_spend_forecast(months_ahead: int = 3, cykliczna: bool | None = None) -> dict:
    """
    Prognoza kosztów całej firmy — patrz _median_seasonal_forecast dla opisu
    metody. `cykliczna`: None = wszystkie faktury, True = tylko kontrahenci
    oznaczeni w KONTRAHENCI_CYKLICZNI (dużo stabilniejsza, przewidywalna
    historia — tu ten baseline ma najwięcej sensu), False = tylko jednorazowe
    (z definicji nieregularne — wskaźnik sezonowości/prognoza tu są dużo mniej
    wiarygodne, ale nadal pokazywane transparentnie zamiast ukrywane).
    """
    today = date.today()
    all_points = db.get_spend_trend(2000, 1, today.year, today.month, cykliczna)
    result = _median_seasonal_forecast(all_points, "brutto", months_ahead)
    result["forecast"] = [{"year": f["year"], "month": f["month"], "brutto": f["value"]} for f in result["forecast"]]
    return result


def _dochod_forecast_from_rows(rows: list, months_ahead: int) -> dict:
    """
    Rdzeń współdzielony przez get_dochod_forecast (jeden dział) i
    get_dochod_forecast_total (suma kilku działów) — patrz
    _median_seasonal_forecast dla opisu metody. Przychód: miesiące bez
    śledzonego przychodu są POMIJANE (nie liczone jako 0) przy budowie
    historii — zerowanie zaniżałoby sezonowość przychodu. Dochód: brak
    przychodu = 0 (dochod = -koszt), spójnie z get_dochod/get_dochod_trend.
    """
    przychod_points = [
        {"year": r["year"], "month": r["month"], "value": r["przychod_netto"]}
        for r in rows if r["przychod_netto"] is not None
    ]
    dochod_points = [
        {"year": r["year"], "month": r["month"], "value": round((r["przychod_netto"] or 0.0) - (r["koszt_netto"] or 0.0), 2)}
        for r in rows
    ]

    przychod_fc = _median_seasonal_forecast(przychod_points, "value", months_ahead)
    dochod_fc = _median_seasonal_forecast(dochod_points, "value", months_ahead)

    return {
        "przychod": {k: v for k, v in przychod_fc.items() if k != "history"},
        "dochod": {k: v for k, v in dochod_fc.items() if k != "history"},
    }


def get_dochod_forecast(dzial: str, months_ahead: int = 3) -> dict:
    """Prognoza przychodu/dochodu JEDNEGO działu (źródło: db.get_dochod(...,
    dzial=dzial)) — patrz _dochod_forecast_from_rows."""
    today = date.today()
    rows = db.get_dochod(2000, 1, today.year, today.month, dzial)
    return {"dzial": dzial, **_dochod_forecast_from_rows(rows, months_ahead)}


def get_dochod_forecast_total(dzialy: list[str], months_ahead: int = 3) -> dict:
    """Jak get_dochod_forecast, ale zsumowane po WSZYSTKICH podanych
    działach — prognoza wyniku "całej firmy" (a ściślej: sumy śledzonych
    brandów) zamiast jednego działu z osobna."""
    today = date.today()
    rows = db.get_dochod(2000, 1, today.year, today.month)
    summed = _sum_dochod_rows(rows, dzialy)
    return {"dzialy": dzialy, **_dochod_forecast_from_rows(summed, months_ahead)}


def _backtest_forecast(points: list, value_field: str, months_back: int) -> list:
    """
    Dla ostatnich `months_back` miesięcy z rzeczywistymi danymi liczy, co
    baseline (patrz _median_seasonal_forecast) przewidziałby dla KAŻDEGO z
    nich, używając WYŁĄCZNIE danych sprzed tego miesiąca — inaczej prognoza
    "widziałaby" własny wynik i porównanie nie miałoby sensu (to klasyczny
    walk-forward backtest, nie podgląd w przyszłość). Odpowiada na pytanie
    "czy model miał rację" dla miesięcy, które już mamy w danych.
    """
    history = _contiguous_history(points)
    if len(history) < 4:
        return []

    start_idx = max(1, len(history) - months_back)
    results = []
    for i in range(start_idx, len(history)):
        prior = history[:i]
        if len(prior) < 3:
            continue
        actual_point = history[i]
        fc = _median_seasonal_forecast(prior, value_field, months_ahead=1)
        if not fc["forecast"]:
            continue
        predicted = fc["forecast"][0]["value"]
        actual = actual_point[value_field]
        diff = round(actual - predicted, 2)
        results.append({
            "year": actual_point["year"],
            "month": actual_point["month"],
            "actual": round(actual, 2),
            "forecast": round(predicted, 2),
            "diff": diff,
            "diff_pct": round(diff / predicted * 100, 1) if predicted else None,
        })
    return results


def get_spend_forecast_backtest(months_back: int = 6, cykliczna: bool | None = None) -> list:
    """Trafność baseline'u kosztów — patrz _backtest_forecast."""
    today = date.today()
    all_points = db.get_spend_trend(2000, 1, today.year, today.month, cykliczna)
    points = [{"year": p["year"], "month": p["month"], "value": p["brutto"]} for p in all_points]
    return _backtest_forecast(points, "value", months_back)


def get_dochod_backtest(dzial: str, months_back: int = 6) -> dict:
    """Trafność baseline'u przychodu/dochodu JEDNEGO działu — patrz
    _backtest_forecast."""
    today = date.today()
    rows = db.get_dochod(2000, 1, today.year, today.month, dzial)
    przychod_points = [
        {"year": r["year"], "month": r["month"], "value": r["przychod_netto"]}
        for r in rows if r["przychod_netto"] is not None
    ]
    dochod_points = [
        {"year": r["year"], "month": r["month"], "value": round((r["przychod_netto"] or 0.0) - (r["koszt_netto"] or 0.0), 2)}
        for r in rows
    ]
    return {
        "dzial": dzial,
        "przychod": _backtest_forecast(przychod_points, "value", months_back),
        "dochod": _backtest_forecast(dochod_points, "value", months_back),
    }


def get_dochod_backtest_total(dzialy: list[str], months_back: int = 6) -> dict:
    """Jak get_dochod_backtest, ale zsumowane po WSZYSTKICH podanych
    działach."""
    today = date.today()
    rows = db.get_dochod(2000, 1, today.year, today.month)
    summed = _sum_dochod_rows(rows, dzialy)
    przychod_points = [
        {"year": r["year"], "month": r["month"], "value": r["przychod_netto"]}
        for r in summed if r["przychod_netto"] is not None
    ]
    dochod_points = [
        {"year": r["year"], "month": r["month"], "value": round((r["przychod_netto"] or 0.0) - (r["koszt_netto"] or 0.0), 2)}
        for r in summed
    ]
    return {
        "dzialy": dzialy,
        "przychod": _backtest_forecast(przychod_points, "value", months_back),
        "dochod": _backtest_forecast(dochod_points, "value", months_back),
    }


def get_podkategoria_breakdown(year_from: int, month_from: int, year_to: int, month_to: int,
                                kategoria: str, dzial: str | None = None, cykliczna: bool | None = None) -> dict:
    # `kategoria` to etykieta kanoniczna scalonej grupy (patrz get_kategoria_breakdown)
    # — trzeba odtworzyć, jakie surowe warianty KATEGORIA do niej należą, żeby
    # dociągnąć podkategorie ze wszystkich, nie tylko z jednego wariantu.
    raw_kategorie = db.get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial, cykliczna)
    target_key = _normalize_label(kategoria)
    variants = [i["kategoria"] for i in raw_kategorie if _normalize_label(i["kategoria"]) == target_key]
    if not variants:
        variants = [kategoria]

    items = _merge_variants(
        db.get_podkategoria_breakdown(year_from, month_from, year_to, month_to, variants, dzial, cykliczna),
        "podkategoria",
    )
    total_brutto = round(sum(i["brutto"] for i in items), 2)
    for i in items:
        i["pct"] = round(i["brutto"] / total_brutto * 100, 1) if total_brutto else 0.0
        del i["_raw_labels"]
    return {"items": items, "total_brutto": total_brutto}


def get_dochod(year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """
    Dochód (przychód netto − koszt netto) per dział, zsumowany za cały
    wybrany okres — plus łączny wynik dla WSZYSTKICH działów. Brak śledzonego
    przychodu liczy się jako 0 zł przychodu (nie "brak danych") — więc dział
    bez przychodu pokazuje dochód na minusie, równy jego kosztowi, dopóki
    użytkownik nie doda dla niego przychodu w Przychody.dbo.Przychod_Netto
    (uzupełnia je stopniowo, patrz [[project_analityka_forecast]]).
    `przychod_netto` samo w sobie zostaje `None`, gdy nic nie jest śledzone —
    to wciąż odróżnia "wiemy że 0" od "jeszcze nie wiemy" — ale `dochod` jest
    zawsze liczbą, żeby dało się uwzględniać wszystkie działy w podsumowaniu.
    """
    rows = db.get_dochod(year_from, month_from, year_to, month_to)

    by_dzial: dict[str, dict] = {}
    for r in rows:
        entry = by_dzial.setdefault(r["dzial"], {"koszt_netto": 0.0, "przychod_netto": 0.0, "ma_przychod": False})
        if r["koszt_netto"] is not None:
            entry["koszt_netto"] += r["koszt_netto"]
        if r["przychod_netto"] is not None:
            entry["przychod_netto"] += r["przychod_netto"]
            entry["ma_przychod"] = True

    items = []
    dzialy_bez_przychodu = []
    total_koszt = total_przychod = 0.0
    for dzial, e in by_dzial.items():
        koszt = round(e["koszt_netto"], 2)
        przychod = round(e["przychod_netto"], 2) if e["ma_przychod"] else None
        dochod = round((przychod or 0.0) - koszt, 2)
        # Marża = dochód/przychód — pozwala porównać RENTOWNOŚĆ działów o
        # różnej skali (Hotel vs RDS w złotówkach nie da się sensownie
        # zestawić, w % owszem). Tylko gdy przychód jest znany i niezerowy —
        # inaczej dzielenie przez 0/brak danych nie ma sensu.
        marza_pct = round(dochod / przychod * 100, 1) if przychod else None
        items.append({
            "dzial": dzial, "koszt_netto": koszt, "przychod_netto": przychod,
            "dochod": dochod, "marza_pct": marza_pct,
        })
        if not e["ma_przychod"]:
            dzialy_bez_przychodu.append(dzial)
        total_koszt += koszt
        total_przychod += (przychod or 0.0)

    items.sort(key=lambda i: i["dochod"], reverse=True)
    dzialy_bez_przychodu.sort()

    total_dochod = round(total_przychod - total_koszt, 2)
    return {
        "items": items,
        "total_koszt_netto": round(total_koszt, 2),
        "total_przychod_netto": round(total_przychod, 2),
        "total_dochod": total_dochod,
        "total_marza_pct": round(total_dochod / total_przychod * 100, 1) if total_przychod else None,
        "dzialy_bez_przychodu": dzialy_bez_przychodu,
    }


def _dochod_rows_by_year(rows: list) -> dict:
    """
    rows: lista {"year","month","koszt_netto","przychod_netto"} — jeden
    wiersz na (rok,miesiąc), już zawężona/zsumowana do żądanego działu albo
    grupy działów. Przestawia w serie po roku (miesiąc 1-12 na osi) — rdzeń
    współdzielony przez get_dochod_trend (jeden dział) i
    get_dochod_trend_total (suma kilku działów).
    """
    by_ym: dict[tuple, dict] = {}
    for r in rows:
        koszt = r["koszt_netto"] or 0.0
        przychod = r["przychod_netto"]
        dochod = round((przychod or 0.0) - koszt, 2)
        by_ym[(r["year"], r["month"])] = {
            "koszt_netto": round(koszt, 2),
            "przychod_netto": round(przychod, 2) if przychod is not None else None,
            "dochod": dochod,
        }

    years = sorted({y for y, m in by_ym})

    def series_for(field: str) -> list:
        return [
            {"year": y, "values": [(by_ym.get((y, m)) or {}).get(field) for m in range(1, 13)]}
            for y in years
        ]

    return {
        "years": years,
        "koszt_by_year": series_for("koszt_netto"),
        "przychod_by_year": series_for("przychod_netto"),
        "dochod_by_year": series_for("dochod"),
    }


def _sum_dochod_rows(rows: list, dzialy: list) -> list:
    """Sumuje wiersze db.get_dochod (per dział+miesiąc) po wskazanych
    działach, zwraca jeden wiersz na miesiąc bez podziału na dział — do
    agregatów typu "wszystkie brandy razem"."""
    by_ym: dict[tuple, dict] = {}
    for r in rows:
        if r["dzial"] not in dzialy:
            continue
        entry = by_ym.setdefault((r["year"], r["month"]), {"koszt_netto": 0.0, "przychod_netto": 0.0, "ma_przychod": False})
        entry["koszt_netto"] += r["koszt_netto"] or 0.0
        if r["przychod_netto"] is not None:
            entry["przychod_netto"] += r["przychod_netto"]
            entry["ma_przychod"] = True
    return [
        {
            "year": y, "month": m,
            "koszt_netto": round(e["koszt_netto"], 2),
            "przychod_netto": round(e["przychod_netto"], 2) if e["ma_przychod"] else None,
        }
        for (y, m), e in by_ym.items()
    ]


def get_dochod_trend(dzial: str, year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Miesięczny koszt/przychód/dochód JEDNEGO działu, przestawiony w serie
    po roku — do porównania "styczeń 2024 vs 2025 vs 2026" na wykresie."""
    rows = db.get_dochod(year_from, month_from, year_to, month_to, dzial)
    return {"dzial": dzial, **_dochod_rows_by_year(rows)}


def get_dochod_trend_total(dzialy: list[str], year_from: int, month_from: int, year_to: int, month_to: int) -> dict:
    """Jak get_dochod_trend, ale zsumowane po WSZYSTKICH podanych działach —
    "wynik całej firmy" (a ściślej: sumy śledzonych brandów) zamiast jednego
    działu z osobna."""
    rows = db.get_dochod(year_from, month_from, year_to, month_to)
    summed = _sum_dochod_rows(rows, dzialy)
    return {"dzialy": dzialy, **_dochod_rows_by_year(summed)}
