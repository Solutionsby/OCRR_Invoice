import pyodbc
import os
from dotenv import load_dotenv
from decimal import Decimal
load_dotenv()

def get_db_connection():
    """Tworzy połączenie z bazą SQL Express na Twoim Macu/Windowsie."""
    try:
        server = os.getenv('DB_SERVER')
        database = os.getenv('DB_NAME')
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            f'SERVER={server};'  
            f'DATABASE={database};'
            f'UID={user};'
            f'PWD={password};'
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
    if not conn: return
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
        
        values = (
            str(data['invoice_number']),
            str(data['firm_name']),
            data['invoice_date'],
            netto,
            vat,
            str(data['dzial']),
            str(data.get('opis', '')),
            str(data.get('kategoria', '')),
            str(data.get('podkategoria', '')),
            kaucja,
        )
        
        cursor.execute(sql, values)
        conn.commit()
        print(f"✅ SQL: Zapisano w FAKTURY_KOSZTOWE (Nr: {data['invoice_number']})")
    except Exception as e:
        print(f"❌ BŁĄD SQL (FAKTURY_KOSZTOWE): {e}")
    finally:
        conn.close()

# --- TABELA 2: FAKTURY_DO_ZAPLATY (Dla Mailera - Tryby T, N, K) ---

def save_to_faktury_do_zaplaty(data):
    """
    Zapisuje fakturę do bazy płatności, z której korzysta mail_sender.py.
    """
    conn = get_db_connection()
    if not conn: return
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
            str(data['file_name']) 
        )
        
        cursor.execute(sql, values)
        conn.commit()
        print(f"✅ SQL: Zapisano w FAKTURY_DO_ZAPLATY.")
    except Exception as e:
        print(f"❌ BŁĄD SQL (FAKTURY_DO_ZAPLATY): {e}")
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