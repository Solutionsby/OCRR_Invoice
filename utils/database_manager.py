import pyodbc
import os
from dotenv import load_dotenv
from decimal import Decimal
load_dotenv()

def get_db_connection():
    """
    Tworzy połączenie z bazą SQL. Nazwa sterownika ODBC pochodzi z DB_DRIVER
    (.env) zamiast być zaszyta na sztywno — na hoscie (CLI) to Driver 17,
    zainstalowany lokalnie; w kontenerze Dockera doinstalowany jest Driver 18
    (patrz Dockerfile), więc docker-compose.yml nadpisuje DB_DRIVER na 18.
    Encrypt=no jawnie, żeby zachowanie nie zależało od domyślnej wartości
    Encrypt, która różni się między Driverem 17 (domyślnie off) i 18
    (domyślnie on, wymaga zaufanego certyfikatu) — bez tego Driver 18
    odmówiłby połączenia z serwerem SQL bez skonfigurowanego TLS.
    """
    try:
        server = os.getenv('DB_SERVER')
        database = os.getenv('DB_NAME')
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        if not driver.startswith('{'):
            driver = f'{{{driver}}}'
        conn = pyodbc.connect(
            f'DRIVER={driver};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={user};'
            f'PWD={password};'
            'Encrypt=no;'
        )
        return conn
    except Exception as e:
        print(f"❌ BŁĄD POŁĄCZENIA Z BAZĄ SQL: {e}")
        return None

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