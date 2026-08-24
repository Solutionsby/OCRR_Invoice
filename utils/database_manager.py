import pyodbc
import os
import threading
import time
from datetime import date
from dotenv import load_dotenv
from decimal import Decimal
load_dotenv()

# Sterownik ODBC ma WŁASNĄ, wewnętrzną pulę połączeń (włączoną domyślnie) —
# przy problemach z zerwanym połączeniem (patrz niżej) potrafiła oddawać
# kolejne MARTWE połączenia z puli zamiast prawdziwie nowych, co dawało
# kaskadę kilkudziesięciu "połączenie padło" pod rząd zamiast jednego udanego
# reconnectu (złapane na żywo 2026-08-24). Ponieważ i tak zarządzamy jednym
# trwałym połączeniem sami (patrz _shared_conn), pula sterownika jest zbędna
# i tylko szkodzi — wyłączona. MUSI być ustawione przed pierwszym connect().
pyodbc.pooling = False

# Nawiązanie połączenia z tym serwerem jest bardzo drogie — zmierzone na
# żywo: samo pyodbc.connect() potrafi zająć >100s, a pierwszy dostęp
# cross-database do bazy Przychody (SQL Server negocjuje dostęp do baz
# źródłowych innych działów) kolejne >30s. Dawniej każda z ~15 funkcji w tym
# pliku otwierała i ZAMYKAŁA własne połączenie — więc ten koszt płaciło się
# praktycznie przy każdym zapytaniu, bo sesja nigdy nie zdążyła zostać
# "rozgrzana" dłużej niż jedno zapytanie (szczegóły pomiarów w
# PLAN_ANALITYKA.md). Teraz jedno połączenie żyje przez cały czas życia
# procesu i jest reużywane.
_conn_lock = threading.Lock()
_shared_conn = None


class _RetryingCursor:
    """
    Cienki wrapper na pyodbc.Cursor: `.execute()` łapie zerwane połączenie
    DOKŁADNIE tam, gdzie realnie występuje, łączy się ponownie i ponawia TO
    SAMO zapytanie raz, zanim odda błąd dalej. Konieczne, bo zaobserwowane na
    żywo: sesja cross-database do Przychody potrafi wygasnąć NIEZALEŻNIE od
    żywotności bazowego połączenia — wcześniejszy wariant z osobnym
    prefetch-checkiem (`SELECT 1`) przechodził, a właściwe zapytanie
    cross-database i tak padało z 10054, więc błąd wracał do użytkownika, a
    naprawa następowała dopiero przy KOLEJNYM, niepowiązanym zapytaniu.
    Zna tylko execute/fetchall/fetchone — jedyne metody cursora używane w
    tym pliku.
    """

    def __init__(self):
        self._cursor = _shared_conn.cursor()

    def execute(self, *args, **kwargs):
        global _shared_conn
        try:
            self._cursor.execute(*args, **kwargs)
        except pyodbc.Error:
            print("⚠️ Zapytanie SQL padło (zerwane połączenie) — łączę ponownie i ponawiam.")
            try:
                _shared_conn.close()  # jawnie oddaj martwe połączenie, nie licz na GC
            except Exception:
                pass
            _shared_conn = _connect_fresh()
            self._cursor = _shared_conn.cursor()
            self._cursor.execute(*args, **kwargs)
        return self

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()


class _SharedConnectionHandle:
    """
    Owija współdzielone połączenie tak, żeby ~15 miejsc w tym pliku mogło
    dalej pisać `conn = get_db_connection(); ...; conn.close()` bez żadnych
    zmian — ale `.close()` NIE zamyka fizycznego połączenia, tylko zwalnia
    `_conn_lock`. Lock (nie tylko reużycie połączenia) jest kluczowy:
    pyodbc.Connection nie jest bezpieczne przy równoległym użyciu z wielu
    wątków, a FastAPI odpala sync endpointy w threadpoolu — bez serializacji
    dwa jednoczesne zapytania cross-database do Przychody dawały żywy
    connection reset (10054) z serwera (złapane 2026-08-24).
    """

    def cursor(self):
        return _RetryingCursor()

    def commit(self):
        _shared_conn.commit()

    def close(self):
        _conn_lock.release()


def _connect_fresh():
    """
    Nazwa sterownika ODBC pochodzi z DB_DRIVER (.env) zamiast być zaszyta na
    sztywno — na hoscie (CLI) to Driver 17, zainstalowany lokalnie; w
    kontenerze Dockera doinstalowany jest Driver 18 (patrz Dockerfile),
    więc docker-compose.yml nadpisuje DB_DRIVER na 18. Encrypt=no jawnie,
    żeby zachowanie nie zależało od domyślnej wartości Encrypt, która różni
    się między Driverem 17 (domyślnie off) i 18 (domyślnie on, wymaga
    zaufanego certyfikatu) — bez tego Driver 18 odmówiłby połączenia z
    serwerem SQL bez skonfigurowanego TLS.
    """
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
    if not driver.startswith('{'):
        driver = f'{{{driver}}}'
    # BEZ jawnego timeout (i connect(), i conn.timeout) pyodbc/ODBC potrafi
    # wisieć W NIESKOŃCZONOŚĆ, jeśli sieć po prostu nie odpowiada zamiast
    # zwrócić błąd — złapane na żywo: cały kontener zablokowany na >12 minut
    # na WSZYSTKICH zapytaniach (nawet niedotykających Przychody), bo lock
    # nigdy się nie zwolnił. `timeout=` ogranicza samo nawiązanie połączenia,
    # `conn.timeout` (ustawione niżej) ogranicza wykonanie KAŻDEGO zapytania
    # na tym połączeniu — oba muszą zamienić "wisi w nieskończoność" w
    # rzucony wyjątek, który _RetryingCursor już umie złapać i naprawić.
    conn = pyodbc.connect(
        f'DRIVER={driver};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={user};'
        f'PWD={password};'
        'Encrypt=no;'
        # Sieć do tego serwera (zwłaszcza z wnętrza kontenera Docker) potrafi
        # zrywać połączenie (10054) — te dwa parametry każą samemu
        # sterownikowi ODBC próbować ponownie połączyć się przy zerwaniu,
        # zanim w ogóle dojdzie do naszego Pythonowego retry na cursorze.
        'ConnectRetryCount=3;'
        'ConnectRetryInterval=5;',
        timeout=180,
    )
    conn.timeout = 90
    return conn


def get_db_connection():
    """
    Zwraca uchwyt do współdzielonego, długo żyjącego połączenia (patrz
    _SharedConnectionHandle) zamiast nawiązywać nowe za każdym razem. Blokuje
    na czas operacji — zwolnienie locka dzieje się w `conn.close()`
    wywoływanym przez każdą z funkcji poniżej w bloku `finally`, więc każde
    wywołanie tej funkcji MUSI kończyć się odpowiadającym `.close()`, inaczej
    lock zostanie zablokowany na stałe.

    Odporność na zerwane połączenie NIE jest tu (prefetch-check typu
    `SELECT 1` nie łapał realnego przypadku — patrz _RetryingCursor) — dzieje
    się przy właściwym zapytaniu, w cursorze zwracanym przez
    `_SharedConnectionHandle.cursor()`.
    """
    global _shared_conn
    _conn_lock.acquire()
    try:
        if _shared_conn is None:
            _shared_conn = _connect_fresh()
        return _SharedConnectionHandle()
    except Exception as e:
        _conn_lock.release()
        print(f"❌ BŁĄD POŁĄCZENIA Z BAZĄ SQL: {e}")
        return None


def _keepalive_loop(interval_seconds):
    """
    Co `interval_seconds` odpytuje `SELECT 1` na współdzielonym połączeniu.
    Złapane na żywo: reset (10054) występował nawet na zwykłych zapytaniach
    NIEDOTYKAJĄCYCH Przychody (np. `/api/mailer/monthly/dzialy`) — to nie
    problem cross-database, tylko zwykły timeout bezczynnego połączenia
    (Docker NAT / firewall / sam SQL Server ubija sesję stojącą bezczynnie
    zbyt długo). Bez tego pętli każda dłuższa przerwa w ruchu = kolejne
    >100s na odbudowanie połączenia przy następnym realnym zapytaniu.
    Uruchamiana jako wątek-daemon z api/main.py przy starcie.
    """
    while True:
        time.sleep(interval_seconds)
        conn = get_db_connection()
        if conn:
            try:
                conn.cursor().execute("SELECT 1")
            except Exception:
                pass
            finally:
                conn.close()


def start_keepalive(interval_seconds=30):
    threading.Thread(target=_keepalive_loop, args=(interval_seconds,), daemon=True).start()

# --- TABELA 1: FAKTURY_KOSZTOWE (Zastępuje CSV - Tryby T i N) ---

def save_to_faktury_kosztowe(data):
    """
    Zapisuje dane do głównej tabeli kosztowej. 
    Mapowanie zgodne ze strukturą ze zdjęcia użytkownika.
    """
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        # Struktura zgodna z Twoim zrzutem ekranu
        sql = """
            INSERT INTO FAKTURY_KOSZTOWE (
                Numer_Faktury, Nazwa_Kontrahenta, Data_Wystwawienia,
                Kwota_Netto, Kwota_Vat, Dzial, Opis, KATEGORIA, PODKATEGORIA, Kaucja
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Konwersja kwot na Decimal (dla typu money w SQL)
        netto = Decimal(str(data.get('netto', 0)).replace(',', '.'))
        vat = Decimal(str(data.get('vat', 0)).replace(',', '.'))
        kaucja = Decimal(str(data.get('kaucja', 0)).replace(',', '.'))

        # Limity kolumn w FAKTURY_KOSZTOWE (varchar) — obcinamy zamiast
        # wywalać cały zapis błędem "String or binary data would be truncated".
        values = (
            str(data['invoice_number'])[:100],
            str(data['firm_name'])[:100],
            data['invoice_date'],
            netto,
            vat,
            str(data['dzial'])[:50],
            str(data.get('opis', ''))[:50],
            str(data.get('kategoria', ''))[:50],
            str(data.get('podkategoria', ''))[:100],
            kaucja,
        )

        cursor.execute(sql, values)
        conn.commit()
        print(f"✅ SQL: Zapisano w FAKTURY_KOSZTOWE (Nr: {data['invoice_number']})")
        return True
    except Exception as e:
        print(f"❌ BŁĄD SQL (FAKTURY_KOSZTOWE): {e}")
        return False
    finally:
        conn.close()

# --- TABELA 2: FAKTURY_DO_ZAPLATY (Dla Mailera - Tryby T, N, K) ---

def save_to_faktury_do_zaplaty(data):
    """
    Zapisuje fakturę do bazy płatności, z której korzysta mail_sender.py.
    W polu NazwaPliku zapisujemy pełną ścieżkę do pliku (nie samą nazwę) —
    mail_sender.py bierze ją bezpośrednio, bez przeszukiwania folderów.
    Zwraca True/False, żeby wywołujący mógł zareagować na wynik zapisu.
    """
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO FAKTURY_DO_ZAPLATY (
                 Kontrahent,
                 NumerFaktury,
                 DataPlatnosci,
                 KwotaBrutto,
                 NazwaPliku,
                 CzyWyslano
            ) VALUES (?, ?, ?, ?, ?, 0)
        """

        brutto = Decimal(str(data.get('brutto', 0)).replace(',', '.'))

        values = (
            str(data['firm_name']),
            str(data['invoice_number']),
            data['payment_date'],
            brutto,
            str(data['file_path'])
        )

        cursor.execute(sql, values)
        conn.commit()
        print(f"✅ SQL: Zapisano w FAKTURY_DO_ZAPLATY.")
        return True
    except Exception as e:
        print(f"❌ BŁĄD SQL (FAKTURY_DO_ZAPLATY): {e}")
        return False
    finally:
        conn.close()

# --- SPRAWDZANIE DUPLIKATÓW (wywoływane przy analizie, przed potwierdzeniem) ---

def find_duplicates(invoice_number):
    """
    Szuka wcześniej zapisanych wpisów o tym samym numerze faktury w obu
    tabelach — pomaga złapać przypadek ponownego przetworzenia tej samej
    faktury (np. powtórnie ściągniętej z KSeF). Dopasowanie tylko po numerze
    (nie po kontrahencie) — operator i tak widzi kontrahenta z dopasowanego
    wiersza i sam oceni, czy to fałszywy alarm (różne firmy mogą teoretycznie
    mieć ten sam numer faktury).
    """
    conn = get_db_connection()
    if not conn or not str(invoice_number).strip() or str(invoice_number).strip().lower() == 'brak':
        return []
    try:
        cursor = conn.cursor()
        matches = []

        cursor.execute(
            "SELECT Id, Kontrahent, NazwaPliku FROM FAKTURY_DO_ZAPLATY WHERE NumerFaktury = ?",
            (str(invoice_number),),
        )
        for row in cursor.fetchall():
            matches.append({
                "tabela": "FAKTURY_DO_ZAPLATY",
                "kontrahent": row.Kontrahent,
                "plik": row.NazwaPliku,
            })

        cursor.execute(
            "SELECT Nazwa_Kontrahenta FROM FAKTURY_KOSZTOWE WHERE Numer_Faktury = ?",
            (str(invoice_number),),
        )
        for row in cursor.fetchall():
            matches.append({
                "tabela": "FAKTURY_KOSZTOWE",
                "kontrahent": row.Nazwa_Kontrahenta,
                "plik": None,
            })

        return matches
    except Exception as e:
        print(f"❌ BŁĄD SQL (find_duplicates): {e}")
        return []
    finally:
        conn.close()

def search_invoices(numer="", kontrahent=""):
    """
    Szuka faktur w obu tabelach po częściowym, niewrażliwym na wielkość liter
    dopasowaniu numeru i/lub kontrahenta — ręczne "czy to już jest w bazie",
    niezależne od aktualnie przeglądanego pliku. Wymaga podania co najmniej
    jednego z dwóch kryteriów (inaczej zwraca pustą listę, żeby nie zrzucać
    całej tabeli).
    """
    numer = (numer or "").strip()
    kontrahent = (kontrahent or "").strip()
    if not numer and not kontrahent:
        return []

    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        results = []

        where, params = [], []
        if numer:
            where.append("NumerFaktury LIKE ?")
            params.append(f"%{numer}%")
        if kontrahent:
            where.append("Kontrahent LIKE ?")
            params.append(f"%{kontrahent}%")
        cursor.execute(
            "SELECT TOP 50 Kontrahent, NumerFaktury, DataPlatnosci, KwotaBrutto, NazwaPliku, CzyWyslano "
            "FROM FAKTURY_DO_ZAPLATY WHERE " + " AND ".join(where) + " ORDER BY Id DESC",
            params,
        )
        for row in cursor.fetchall():
            results.append({
                "tabela": "FAKTURY_DO_ZAPLATY",
                "numer_faktury": row.NumerFaktury,
                "kontrahent": row.Kontrahent,
                "data": str(row.DataPlatnosci) if row.DataPlatnosci else None,
                "kwota": float(row.KwotaBrutto) if row.KwotaBrutto is not None else None,
                "plik": row.NazwaPliku,
                "wyslano": bool(row.CzyWyslano) if row.CzyWyslano is not None else None,
            })

        where2, params2 = [], []
        if numer:
            where2.append("Numer_Faktury LIKE ?")
            params2.append(f"%{numer}%")
        if kontrahent:
            where2.append("Nazwa_Kontrahenta LIKE ?")
            params2.append(f"%{kontrahent}%")
        cursor.execute(
            "SELECT TOP 50 Nazwa_Kontrahenta, Numer_Faktury, Data_Wystwawienia, Kwota_Netto, Kwota_Vat "
            "FROM FAKTURY_KOSZTOWE WHERE " + " AND ".join(where2) + " ORDER BY Data_Wprowadzenia DESC",
            params2,
        )
        for row in cursor.fetchall():
            netto = float(row.Kwota_Netto) if row.Kwota_Netto is not None else 0.0
            vat = float(row.Kwota_Vat) if row.Kwota_Vat is not None else 0.0
            results.append({
                "tabela": "FAKTURY_KOSZTOWE",
                "numer_faktury": row.Numer_Faktury,
                "kontrahent": row.Nazwa_Kontrahenta,
                "data": str(row.Data_Wystwawienia) if row.Data_Wystwawienia else None,
                "kwota": round(netto + vat, 2),
                "plik": None,
                "wyslano": None,
            })

        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (search_invoices): {e}")
        return []
    finally:
        conn.close()

def get_kosztowe_by_month(year, month):
    """
    Wiersze widoku Faktury.dbo.Faktury_Kosztowe_Zmapowane za dany miesiąc
    (Data_Wystwawienia) — źródło podsumowania Excel dla comiesięcznej pełnej
    paczki mailera (i raportu właściciela, patrz core/monthly_report.py).
    Ten widok ma dokładnie te same wiersze co FAKTURY_KOSZTOWE (zweryfikowane
    live: identyczna liczba wierszy i suma za czerwiec 2026), plus kolumnę
    `dzial_docelowy` — zmapowany, dużo krótszy zestaw działów (9 zamiast 20
    surowych wartości `Dzial`, np. "RDS DRUK"/"KI DRUK" składają się w jeden
    "RDS"/"Konrad") — właśnie ten podział ma sens dla raportu właściciela.
    Obejmuje wszystkie rodzaje faktur: KSeF (zewnętrznym kanałem, poza tym
    narzędziem) oraz "inne"/EUR (zapisywane wprost przez core/inne.py i
    core/euro.py), więc nie trzeba osobno odpytywać FAKTURY_DO_ZAPLATY.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Nazwa_Kontrahenta, Numer_Faktury, Data_Wystwawienia, Kwota_Netto, Kwota_Vat, dzial_docelowy "
            "FROM Faktury_Kosztowe_Zmapowane WHERE YEAR(Data_Wystwawienia) = ? AND MONTH(Data_Wystwawienia) = ? "
            "ORDER BY Data_Wystwawienia, Nazwa_Kontrahenta",
            (year, month),
        )
        results = []
        for row in cursor.fetchall():
            netto = float(row.Kwota_Netto) if row.Kwota_Netto is not None else 0.0
            vat = float(row.Kwota_Vat) if row.Kwota_Vat is not None else 0.0
            data_wyst = row.Data_Wystwawienia
            results.append({
                "firm_name": row.Nazwa_Kontrahenta,
                "invoice_number": row.Numer_Faktury,
                "invoice_date": data_wyst.strftime("%Y-%m-%d") if hasattr(data_wyst, "strftime") else str(data_wyst or ""),
                "netto": netto,
                "vat": vat,
                "dzial": (row.dzial_docelowy or "").strip() or "(brak działu)",
            })
        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_kosztowe_by_month): {e}")
        return []
    finally:
        conn.close()


# --- ANALITYKA (widok Faktury_Kosztowe_Zmapowane, agregacje po stronie SQL) ---

def _month_range_bounds(year_from, month_from, year_to, month_to):
    """
    (data_od, data_do_wyłącznie) dla zakresu miesięcy — tolerancyjne na
    odwrócony zakres (od > do), tak samo jak core/monthly_report.py, żeby
    obie warstwy zgadzały się co do znaczenia "od"/"do". Górna granica jest
    wyłączna (< data_do), żeby uniknąć zależności od funkcji SQL
    EOMONTH/DATEADD po stronie zapytania.
    """
    start = year_from * 12 + (month_from - 1)
    end = year_to * 12 + (month_to - 1)
    if end < start:
        start, end = end, start
    date_from = date(start // 12, start % 12 + 1, 1)
    end_y, end_m = end // 12, end % 12 + 1
    date_to = date(end_y + 1, 1, 1) if end_m == 12 else date(end_y, end_m + 1, 1)
    return date_from, date_to


def get_spend_trend(year_from, month_from, year_to, month_to, cykliczna=None):
    """Suma netto/VAT/liczba faktur per rok-miesiąc w zadanym oknie —
    źródło wykresu trendu kosztów w czasie (zakładka „Trend” analityki).
    `cykliczna`: None = wszystkie, True = tylko CzyCykliczna=1 (kontrahenci
    oznaczeni w KONTRAHENCI_CYKLICZNI), False = tylko jednorazowe."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        where = "WHERE Data_Wystwawienia >= ? AND Data_Wystwawienia < ?"
        params = [date_from, date_to]
        if cykliczna is not None:
            where += " AND CzyCykliczna = ?"
            params.append(1 if cykliczna else 0)
        cursor.execute(
            "SELECT YEAR(Data_Wystwawienia) AS yr, MONTH(Data_Wystwawienia) AS mo, "
            "SUM(Kwota_Netto) AS netto, SUM(Kwota_Vat) AS vat, COUNT(*) AS cnt "
            f"FROM Faktury_Kosztowe_Zmapowane {where} "
            "GROUP BY YEAR(Data_Wystwawienia), MONTH(Data_Wystwawienia) "
            "ORDER BY yr, mo",
            params,
        )
        results = []
        for row in cursor.fetchall():
            netto = float(row.netto) if row.netto is not None else 0.0
            vat = float(row.vat) if row.vat is not None else 0.0
            results.append({
                "year": row.yr, "month": row.mo,
                "netto": round(netto, 2), "vat": round(vat, 2),
                "brutto": round(netto + vat, 2), "count": row.cnt,
            })
        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_spend_trend): {e}")
        return []
    finally:
        conn.close()


def get_top_kontrahenci(year_from, month_from, year_to, month_to, limit=15, dzial=None):
    """Ranking kontrahentów wg sumy brutto w oknie + suma całkowita okresu
    (do liczenia % udziału, także dla kontrahentów spoza TOP N). Opcjonalny
    filtr dzial_docelowy — "kto najwięcej kosztuje w tym dziale"."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    conn = get_db_connection()
    if not conn:
        return [], 0.0
    try:
        cursor = conn.cursor()
        where = "WHERE Data_Wystwawienia >= ? AND Data_Wystwawienia < ?"
        params = [date_from, date_to]
        if dzial:
            where += " AND dzial_docelowy = ?"
            params.append(dzial)

        cursor.execute(
            f"SELECT SUM(ISNULL(Kwota_Netto,0) + ISNULL(Kwota_Vat,0)) AS brutto "
            f"FROM Faktury_Kosztowe_Zmapowane {where}",
            params,
        )
        total_row = cursor.fetchone()
        total_brutto = float(total_row.brutto) if total_row and total_row.brutto is not None else 0.0

        cursor.execute(
            f"SELECT TOP (?) Nazwa_Kontrahenta, SUM(ISNULL(Kwota_Netto,0) + ISNULL(Kwota_Vat,0)) AS brutto, COUNT(*) AS cnt "
            f"FROM Faktury_Kosztowe_Zmapowane {where} "
            "GROUP BY Nazwa_Kontrahenta "
            "ORDER BY brutto DESC",
            [limit, *params],
        )
        items = []
        for row in cursor.fetchall():
            brutto = float(row.brutto) if row.brutto is not None else 0.0
            items.append({
                "kontrahent": row.Nazwa_Kontrahenta, "brutto": round(brutto, 2), "count": row.cnt,
                "pct": round(brutto / total_brutto * 100, 1) if total_brutto else 0.0,
            })
        return items, round(total_brutto, 2)
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_top_kontrahenci): {e}")
        return [], 0.0
    finally:
        conn.close()


def get_dzial_trend(year_from, month_from, year_to, month_to):
    """Suma brutto per rok-miesiąc-dział_docelowy — źródło wykresu struktury
    kosztów wg działu w czasie (zakładka „Działy” analityki)."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT YEAR(Data_Wystwawienia) AS yr, MONTH(Data_Wystwawienia) AS mo, "
            "COALESCE(NULLIF(LTRIM(RTRIM(dzial_docelowy)), ''), '(brak działu)') AS dzial, "
            "SUM(ISNULL(Kwota_Netto,0) + ISNULL(Kwota_Vat,0)) AS brutto "
            "FROM Faktury_Kosztowe_Zmapowane "
            "WHERE Data_Wystwawienia >= ? AND Data_Wystwawienia < ? "
            "GROUP BY YEAR(Data_Wystwawienia), MONTH(Data_Wystwawienia), "
            "COALESCE(NULLIF(LTRIM(RTRIM(dzial_docelowy)), ''), '(brak działu)') "
            "ORDER BY yr, mo",
            (date_from, date_to),
        )
        results = []
        for row in cursor.fetchall():
            brutto = float(row.brutto) if row.brutto is not None else 0.0
            results.append({"year": row.yr, "month": row.mo, "dzial": row.dzial, "brutto": round(brutto, 2)})
        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_dzial_trend): {e}")
        return []
    finally:
        conn.close()


def get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial=None, cykliczna=None):
    """Suma brutto per KATEGORIA w oknie, opcjonalnie zawężona do jednego
    dzial_docelowy i/lub cykliczne/jednorazowe — zakładka „Kategorie” analityki."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        where = "WHERE Data_Wystwawienia >= ? AND Data_Wystwawienia < ?"
        params = [date_from, date_to]
        if dzial:
            where += " AND dzial_docelowy = ?"
            params.append(dzial)
        if cykliczna is not None:
            where += " AND CzyCykliczna = ?"
            params.append(1 if cykliczna else 0)
        cursor.execute(
            "SELECT COALESCE(NULLIF(LTRIM(RTRIM(KATEGORIA)), ''), '(brak kategorii)') AS kategoria, "
            "SUM(ISNULL(Kwota_Netto,0) + ISNULL(Kwota_Vat,0)) AS brutto, COUNT(*) AS cnt "
            f"FROM Faktury_Kosztowe_Zmapowane {where} "
            "GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(KATEGORIA)), ''), '(brak kategorii)') "
            "ORDER BY brutto DESC",
            params,
        )
        results = []
        for row in cursor.fetchall():
            brutto = float(row.brutto) if row.brutto is not None else 0.0
            results.append({"kategoria": row.kategoria, "brutto": round(brutto, 2), "count": row.cnt})
        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_kategoria_breakdown): {e}")
        return []
    finally:
        conn.close()


def get_podkategoria_breakdown(year_from, month_from, year_to, month_to, kategoria_variants, dzial=None, cykliczna=None):
    """Jak get_kategoria_breakdown, ale drill-down w PODKATEGORIA w ramach
    wybranej KATEGORIA. `kategoria_variants` to LISTA surowych wartości
    KATEGORIA (nie jedna etykieta) — core/analytics.py scala warianty tej
    samej kategorii różniące się tylko pisownią (patrz _merge_variants), więc
    żeby drill-down objął WSZYSTKIE faktury tej grupy, filtr musi dopasować
    każdy z tych wariantów, nie tylko wybraną (kanoniczną) etykietę."""
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(kategoria_variants))
        where = (
            "WHERE Data_Wystwawienia >= ? AND Data_Wystwawienia < ? "
            f"AND COALESCE(NULLIF(LTRIM(RTRIM(KATEGORIA)), ''), '(brak kategorii)') IN ({placeholders})"
        )
        params = [date_from, date_to, *kategoria_variants]
        if dzial:
            where += " AND dzial_docelowy = ?"
            params.append(dzial)
        if cykliczna is not None:
            where += " AND CzyCykliczna = ?"
            params.append(1 if cykliczna else 0)
        cursor.execute(
            "SELECT COALESCE(NULLIF(LTRIM(RTRIM(PODKATEGORIA)), ''), '(brak podkategorii)') AS podkategoria, "
            "SUM(ISNULL(Kwota_Netto,0) + ISNULL(Kwota_Vat,0)) AS brutto, COUNT(*) AS cnt "
            f"FROM Faktury_Kosztowe_Zmapowane {where} "
            "GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(PODKATEGORIA)), ''), '(brak podkategorii)') "
            "ORDER BY brutto DESC",
            params,
        )
        results = []
        for row in cursor.fetchall():
            brutto = float(row.brutto) if row.brutto is not None else 0.0
            results.append({"podkategoria": row.podkategoria, "brutto": round(brutto, 2), "count": row.cnt})
        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_podkategoria_breakdown): {e}")
        return []
    finally:
        conn.close()


def get_dochod(year_from, month_from, year_to, month_to, dzial=None):
    """
    Zestawienie koszt netto / przychód netto per dział i miesiąc — łączy
    (cross-database, w jednym zapytaniu na tym samym serwerze SQL)
    Faktury_Kosztowe_Zmapowane (koszty) z Przychody.dbo.Przychod_Netto
    (przychody). Wymaga, żeby login aplikacji miał SELECT na bazie Przychody
    (i na bazach źródłowych, jeśli Przychod_Netto jest widokiem odpytującym
    inne bazy) — bez tego cała funkcja padnie wyjątkiem.

    FULL OUTER JOIN celowo — dział może mieć koszt bez śledzonego jeszcze
    przychodu (większość działów dziś) albo (rzadziej) przychód bez kosztu w
    danym miesiącu. Brakująca strona wraca jako None w wyniku Pythona, NIE
    jako 0 — 0 sugerowałoby fałszywy dochód/stratę, podczas gdy naprawdę nie
    mamy tych danych. Odróżnianie „brak danych” od „zero” zostawione
    core/analytics.py.

    Opcjonalny `dzial` (filtr na obu CTE) — zawęża do jednego działu, np. dla
    trendu miesięcznego z porównaniem lat (patrz get_dochod_trend).
    """
    date_from, date_to = _month_range_bounds(year_from, month_from, year_to, month_to)

    start = year_from * 12 + (month_from - 1)
    end = year_to * 12 + (month_to - 1)
    if end < start:
        start, end = end, start
    start_key = (start // 12) * 100 + (start % 12 + 1)
    end_key = (end // 12) * 100 + (end % 12 + 1)

    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        koszty_where = "WHERE Data_Wystwawienia >= ? AND Data_Wystwawienia < ?"
        przychody_where = "WHERE (Rok * 100 + Miesiac) >= ? AND (Rok * 100 + Miesiac) <= ?"
        params = [date_from, date_to, start_key, end_key]
        if dzial:
            koszty_where += " AND COALESCE(NULLIF(LTRIM(RTRIM(dzial_docelowy)), ''), '(brak działu)') = ?"
            przychody_where += " AND Dzial = ?"
            params = [date_from, date_to, dzial, start_key, end_key, dzial]

        cursor.execute(
            f"""
            WITH koszty AS (
                SELECT
                    COALESCE(NULLIF(LTRIM(RTRIM(dzial_docelowy)), ''), '(brak działu)') AS Dzial,
                    YEAR(Data_Wystwawienia) AS Rok, MONTH(Data_Wystwawienia) AS Miesiac,
                    SUM(ISNULL(Kwota_Netto, 0)) AS Koszt_Netto
                FROM Faktury_Kosztowe_Zmapowane
                {koszty_where}
                GROUP BY COALESCE(NULLIF(LTRIM(RTRIM(dzial_docelowy)), ''), '(brak działu)'),
                         YEAR(Data_Wystwawienia), MONTH(Data_Wystwawienia)
            ),
            przychody AS (
                SELECT Dzial, Rok, Miesiac, SUM(KwotaNetto) AS Przychod_Netto
                FROM Przychody.dbo.Przychod_Netto
                {przychody_where}
                GROUP BY Dzial, Rok, Miesiac
            )
            SELECT
                COALESCE(k.Dzial, p.Dzial) AS Dzial,
                COALESCE(k.Rok, p.Rok) AS Rok,
                COALESCE(k.Miesiac, p.Miesiac) AS Miesiac,
                k.Koszt_Netto,
                p.Przychod_Netto
            FROM koszty k
            FULL OUTER JOIN przychody p
                ON k.Dzial = p.Dzial AND k.Rok = p.Rok AND k.Miesiac = p.Miesiac
            ORDER BY Rok, Miesiac, Dzial
            """,
            params,
        )
        results = []
        for row in cursor.fetchall():
            results.append({
                "dzial": row.Dzial,
                "year": row.Rok,
                "month": row.Miesiac,
                "koszt_netto": round(float(row.Koszt_Netto), 2) if row.Koszt_Netto is not None else None,
                "przychod_netto": round(float(row.Przychod_Netto), 2) if row.Przychod_Netto is not None else None,
            })
        return results
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_dochod): {e}")
        return []
    finally:
        conn.close()


# --- FUNKCJE DLA SKRYPTU MAIL_SENDER.PY ---

def mark_as_sent(id_list):
    """
    Aktualizuje status wysyłki w bazie płatności.
    Dodaje CzyWyslano = 1 oraz datę wysyłki.
    """
    conn = get_db_connection()
    if not conn or not id_list: return
    try:
        cursor = conn.cursor()
        # Używamy GETDATE() dla SQL Server, aby zapisać czas wysyłki
        sql = "UPDATE FAKTURY_DO_ZAPLATY SET CzyWyslano = 1, DataWysylki = GETDATE() WHERE Id = ?"
        
        for fid in id_list:
            cursor.execute(sql, (fid,))
            
        conn.commit()
        print(f"✅ SQL: Oznaczono {len(id_list)} faktur jako wysłane.")
    except Exception as e:
        print(f"❌ BŁĄD SQL (mark_as_sent): {e}")
    finally:
        conn.close()


def get_payments_by_ids(id_list):
    """
    Pobiera konkretne pozycje z FAKTURY_DO_ZAPLATY po Id — używane, gdy
    operator ręcznie odznaczył część faktur w przeglądarce przed wysyłką
    (zamiast wysyłać wszystko, co akurat pasuje do okna dni).
    """
    conn = get_db_connection()
    if not conn or not id_list:
        return []
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(id_list))
        cursor.execute(
            f"SELECT Id, Kontrahent, NumerFaktury, DataPlatnosci, KwotaBrutto, NazwaPliku "
            f"FROM FAKTURY_DO_ZAPLATY WHERE Id IN ({placeholders})",
            list(id_list),
        )
        return [
            {
                "id": row.Id,
                "firm_name": row.Kontrahent,
                "invoice_number": row.NumerFaktury,
                "payment_date": row.DataPlatnosci.strftime("%Y-%m-%d") if row.DataPlatnosci else "brak",
                "brutto": float(row.KwotaBrutto) if row.KwotaBrutto is not None else 0.0,
                "file_name": row.NazwaPliku,
            }
            for row in cursor.fetchall()
        ]
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_payments_by_ids): {e}")
        return []
    finally:
        conn.close()


def get_sent_history(limit=50):
    """Ostatnio wysłane przypomnienia — do zakładki historii w przeglądarce."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT TOP (?) Kontrahent, NumerFaktury, KwotaBrutto, DataWysylki "
            "FROM FAKTURY_DO_ZAPLATY WHERE CzyWyslano = 1 ORDER BY DataWysylki DESC",
            (limit,),
        )
        return [
            {
                "firm_name": row.Kontrahent,
                "invoice_number": row.NumerFaktury,
                "brutto": float(row.KwotaBrutto) if row.KwotaBrutto is not None else 0.0,
                "sent_at": row.DataWysylki.strftime("%Y-%m-%d %H:%M") if row.DataWysylki else None,
            }
            for row in cursor.fetchall()
        ]
    except Exception as e:
        print(f"❌ BŁĄD SQL (get_sent_history): {e}")
        return []
    finally:
        conn.close()