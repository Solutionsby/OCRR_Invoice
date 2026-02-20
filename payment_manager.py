import pyodbc
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    conn_str = (
        f"DRIVER={os.getenv('DB_DRIVER')};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_NAME')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)

def load_upcoming_payments_from_sql():
    """Pobiera faktury do opłacenia (niezapłacone, termin do 7 dni)."""
    upcoming = []
    total_sum = 0
    # Termin: od dziś do 7 dni w przód
    limit_date = (datetime.now() + timedelta(days=7)).date()

    query = """
        SELECT Id, Kontrahent, NumerFaktury, DataPlatnosci, KwotaBrutto, Dzial, NazwaPliku
        FROM FAKTURY_DO_ZAPLATY
        WHERE CzyZaplacona = 0 
        AND DataPlatnosci <= ?
        ORDER BY DataPlatnosci ASC
    """

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (limit_date,))
        
        rows = cursor.fetchall()
        for row in rows:
            # Mapowanie kolumn z zapytania
            item = {
                'id': row[0],
                'firm_name': row[1],
                'invoice_number': row[2],
                'payment_date': row[3].strftime("%Y-%m-%d") if row[3] else "brak",
                'brutto': float(row[4]) if row[4] else 0.0,
                'dzial': row[5],
                'file_name': row[6]  # Pełna nazwa pliku PDF z bazy
            }
            upcoming.append(item)
            total_sum += item['brutto']
            
    except Exception as e:
        print(f"❌ BŁĄD SQL (Pobieranie płatności): {e}")
    finally:
        if conn: conn.close()

    return upcoming, total_sum