import os
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# pymongo.MongoClient zarządza własną pulą połączeń i jest bezpieczny do
# współdzielenia między wątkami (w odróżnieniu od pyodbc — patrz
# database_manager.py) — jeden klient na cały czas życia procesu wystarczy,
# bez locków/heartbeatów, które musieliśmy dobudować dla SQL Servera.
_client = None


def _get_incomes_collection():
    global _client
    if _client is None:
        _client = MongoClient(os.getenv("MONGO_URI"))
    return _client.get_default_database()["incomes"]


_INCOMES_PROJECTION = {
    "nazwa": 1, "kwotaBrutto": 1, "kwotaNetto": 1, "kwotaVat": 1, "stawkaVat": 1,
    "typDokumentu": 1, "formaPatnosci": 1, "nrParagonu": 1, "numerFaktury": 1,
    "dataWystawienia": 1, "createdAt": 1,
}

# System hotelowy synchronizuje tę kolekcję okresowymi pełnymi eksportami,
# które potrafią się nakładać oknem czasowym (np. eksport 25.08 objął
# 22.06-23.08, a kolejny 01.09 cały sierpień od nowa) — te same dokumenty
# trafiają wtedy do bazy DRUGI RAZ jako nowe wiersze (inny _id, inny lp,
# ten sam nrParagonu/treść), co bez deduplikacji podwaja przychód
# (potwierdzone na żywych danych: sierpień 2026 pokazywał >1,06 mln zamiast
# ~552 tys.). Jeden przebieg synchronizacji zapisuje wszystkie swoje
# dokumenty w kilku paczkach po ~250 sztuk w odstępach pojedynczych sekund;
# odstęp między RÓŻNYMI przebiegami to zawsze dni/tygodnie — stąd bezpieczny
# próg klastrowania 1h. Kluczem tożsamości pozycji jest nrParagonu (może mieć
# kilka wierszy — pozycje jednego paragonu, w tym CELOWO powtórzone te same
# produkty w tej samej cenie), a dla dokumentów bez numeru paragonu (faktury
# wystawione wprost, bez powiązanego paragonu) — numerFaktury, z tego samego
# powodu (jedna faktura też potrafi mieć kilka pozycji — sprawdzone na żywych
# danych). Każdy dokument w kolekcji ma jedno z tych dwóch pól wypełnione;
# dopasowanie po pełnej treści zostaje tylko jako ostatnia deska ratunku,
# gdyby kiedyś trafił się dokument bez żadnego z nich. Dla każdego klucza
# zatrzymujemy WSZYSTKIE wiersze z jego najnowszego przebiegu i odrzucamy
# wiersze ze starszych przebiegów — to zachowuje legalne duplikaty w obrębie
# jednego przebiegu (wielopozycyjny paragon, dwie identyczne rezerwacje w tym
# samym eksporcie) i usuwa tylko powtórki między przebiegami.
_RUN_GAP_SECONDS = 3600


def _dedupe_incomes(docs: list[dict]) -> list[dict]:
    if not docs:
        return docs

    by_created = sorted(docs, key=lambda d: d["createdAt"])
    run_of_id = {}
    run_idx = 0
    prev_created = by_created[0]["createdAt"]
    for d in by_created:
        if (d["createdAt"] - prev_created).total_seconds() >= _RUN_GAP_SECONDS:
            run_idx += 1
        run_of_id[d["_id"]] = run_idx
        prev_created = d["createdAt"]

    def identity_key(d):
        nr = d.get("nrParagonu")
        if nr:
            return ("nr", nr)
        nf = d.get("numerFaktury")
        if nf:
            return ("faktura", nf)
        return (
            "content",
            d.get("dataWystawienia"), d.get("nazwa"), d.get("kwotaBrutto"),
            d.get("kwotaNetto"), d.get("kwotaVat"), d.get("stawkaVat"),
            d.get("typDokumentu"), d.get("formaPatnosci"),
        )

    latest_run_by_key = {}
    for d in docs:
        key = identity_key(d)
        run = run_of_id[d["_id"]]
        if key not in latest_run_by_key or run > latest_run_by_key[key]:
            latest_run_by_key[key] = run

    return [d for d in docs if run_of_id[d["_id"]] == latest_run_by_key[identity_key(d)]]


def _month_range_bounds(year_from, month_from, year_to, month_to):
    """(data_od, data_do_wyłącznie) jako datetime — MongoDB/BSON porównuje
    daty jako datetime, nie date. Tolerancyjne na odwrócony zakres, tak samo
    jak analogiczna funkcja w utils/database_manager.py."""
    start = year_from * 12 + (month_from - 1)
    end = year_to * 12 + (month_to - 1)
    if end < start:
        start, end = end, start
    date_from = datetime(start // 12, start % 12 + 1, 1)
    end_y, end_m = end // 12, end % 12 + 1
    date_to = datetime(end_y + 1, 1, 1) if end_m == 12 else datetime(end_y, end_m + 1, 1)
    return date_from, date_to


def _fetch_deduped_incomes(date_from, date_to):
    coll = _get_incomes_collection()
    cursor = coll.find({"dataWystawienia": {"$gte": date_from, "$lt": date_to}}, _INCOMES_PROJECTION)
    return _dedupe_incomes(list(cursor))


def get_incomes_trend(year_from, month_from, year_to, month_to):
    """Suma brutto/netto per rok-miesiąc z kolekcji incomes (paragony/
    faktury/anulacje/korekty razem — anulacje i korekty mają już ujemne
    kwoty w bazie, więc zwykłe SUM daje poprawny wynik netto bez żadnego
    dodatkowego filtrowania typDokumentu, zweryfikowane na żywych danych).
    Agregacja liczona w Pythonie (nie w pipeline Mongo), bo najpierw trzeba
    odfiltrować duplikaty z re-syncu — patrz _dedupe_incomes."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    docs = _fetch_deduped_incomes(date_from, date_to)

    by_month: dict[tuple[int, int], dict] = {}
    for d in docs:
        dt = d["dataWystawienia"]
        key = (dt.year, dt.month)
        m = by_month.setdefault(key, {"year": dt.year, "month": dt.month, "brutto": 0.0, "netto": 0.0, "count": 0})
        m["brutto"] += d.get("kwotaBrutto") or 0.0
        m["netto"] += d.get("kwotaNetto") or 0.0
        m["count"] += 1

    results = sorted(by_month.values(), key=lambda m: (m["year"], m["month"]))
    for m in results:
        m["brutto"] = round(m["brutto"], 2)
        m["netto"] = round(m["netto"], 2)
    return results


def get_incomes_raw(year_from, month_from, year_to, month_to):
    """Surowe wiersze (nazwa, kwoty, data) w oknie, po deduplikacji — źródło
    do grupowania per pozycja sprzedaży po stronie core/hotel_analytics.py
    (normalizacja nazw robiona w Pythonie, nie w agregacji Mongo — łatwiej
    testować i utrzymać, tak samo jak scalanie KATEGORII po stronie SQL)."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    docs = _fetch_deduped_incomes(date_from, date_to)
    return [
        {
            "nazwa": doc.get("nazwa") or "",
            "brutto": doc.get("kwotaBrutto") or 0.0,
            "netto": doc.get("kwotaNetto") or 0.0,
            "year": doc["dataWystawienia"].year,
            "month": doc["dataWystawienia"].month,
        }
        for doc in docs
    ]


def get_incomes_by_payment_method(year_from, month_from, year_to, month_to):
    """Suma brutto/count per rok-miesiąc-forma_płatności, po deduplikacji —
    źródło zakładki Płatności. Grupowanie w Pythonie (nie w Mongo), bo
    najpierw trzeba odfiltrować duplikaty z re-syncu — patrz _dedupe_incomes.
    formaPatnosci bywa puste (kilka wierszy w źródle) — trafia pod etykietę
    "(brak danych)", żeby nie zniknęło cicho z sumy."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    docs = _fetch_deduped_incomes(date_from, date_to)

    by_month_method: dict[tuple[int, int], dict[str, dict]] = {}
    for d in docs:
        dt = d["dataWystawienia"]
        method = d.get("formaPatnosci") or "(brak danych)"
        month_bucket = by_month_method.setdefault((dt.year, dt.month), {})
        m = month_bucket.setdefault(method, {"brutto": 0.0, "count": 0})
        m["brutto"] += d.get("kwotaBrutto") or 0.0
        m["count"] += 1
    return by_month_method


def get_incomes_records(year_from, month_from, year_to, month_to):
    """Wszystkie surowe wiersze w oknie (bez deduplikacji) — do ręcznego
    przeglądu w UI. Każdy wiersz oznaczony `is_duplicate`, jeśli
    _dedupe_incomes by go odrzucił — czyli jeśli w tym samym oknie istnieje
    nowszy przebieg synchronizacji z tym samym nrParagonu/treścią. Pozwala
    użytkownikowi zweryfikować wzrokiem i skasować pojedyncze rekordy
    (patrz delete_income_record), zamiast ufać wyłącznie automatycznej
    regule."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    coll = _get_incomes_collection()
    docs = list(coll.find({"dataWystawienia": {"$gte": date_from, "$lt": date_to}}, _INCOMES_PROJECTION))
    kept_ids = {d["_id"] for d in _dedupe_incomes(docs)}
    docs.sort(key=lambda d: (d["dataWystawienia"], d["createdAt"]))
    return [
        {
            "id": str(d["_id"]),
            "nrParagonu": d.get("nrParagonu") or "",
            "numerFaktury": d.get("numerFaktury") or "",
            "nazwa": d.get("nazwa") or "",
            "kwotaBrutto": d.get("kwotaBrutto") or 0.0,
            "kwotaNetto": d.get("kwotaNetto") or 0.0,
            "typDokumentu": d.get("typDokumentu") or "",
            "formaPatnosci": d.get("formaPatnosci") or "",
            "dataWystawienia": d["dataWystawienia"].isoformat(),
            "createdAt": d["createdAt"].isoformat(),
            "is_duplicate": d["_id"] not in kept_ids,
        }
        for d in docs
    ]


def delete_income_record(record_id: str) -> bool:
    """Kasuje pojedynczy dokument z `incomes` po _id. Nieodwracalne — wołane
    tylko z UI przeglądu rekordów, po ręcznym potwierdzeniu przez
    użytkownika, że dany wiersz to faktyczny duplikat."""
    try:
        oid = ObjectId(record_id)
    except InvalidId:
        return False
    coll = _get_incomes_collection()
    result = coll.delete_one({"_id": oid})
    return result.deleted_count > 0
