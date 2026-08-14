from datetime import datetime, timedelta

from utils.database_manager import get_db_connection

def load_upcoming_payments_from_sql(days_window: int = 7, ignore_date_window: bool = False):
    """
    Pobiera faktury do opłacenia: niezapłacone. Domyślnie ograniczone do okna
    +/-days_window dni od dziś (dolna granica chroni przed pominięciem czegoś,
    co dopiero co trafiło do bazy z terminem tuż w przeszłości, górna to zwykłe
    "najbliższy tydzień"). ignore_date_window=True wyłącza to ograniczenie
    i zwraca WSZYSTKIE niezapłacone faktury bez względu na termin.
    """
    upcoming = []
    total_sum = 0

    if ignore_date_window:
        query = """
            SELECT Id, Kontrahent, NumerFaktury, DataPlatnosci, KwotaBrutto, NazwaPliku
            FROM FAKTURY_DO_ZAPLATY
            WHERE CzyZaplacona = 0 AND CzyWyslano = 0
            ORDER BY DataPlatnosci ASC
        """
        params = ()
    else:
        today = datetime.now().date()
        lower_bound = today - timedelta(days=days_window)
        upper_bound = today + timedelta(days=days_window)
        query = """
            SELECT Id, Kontrahent, NumerFaktury, DataPlatnosci, KwotaBrutto, NazwaPliku
            FROM FAKTURY_DO_ZAPLATY
            WHERE CzyZaplacona = 0 AND CzyWyslano = 0
            AND DataPlatnosci >= ?
            AND DataPlatnosci <= ?
            ORDER BY DataPlatnosci ASC
        """
        params = (lower_bound, upper_bound)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)

        rows = cursor.fetchall()
        for row in rows:
            # Mapowanie kolumn z zapytania
            item = {
                'id': row[0],
                'firm_name': row[1],
                'invoice_number': row[2],
                'payment_date': row[3].strftime("%Y-%m-%d") if row[3] else "brak",
                'brutto': float(row[4]) if row[4] else 0.0,
                'file_name': row[5]  # Pełna ścieżka do pliku PDF z bazy
            }
            upcoming.append(item)
            total_sum += item['brutto']
            
    except Exception as e:
        print(f"❌ BŁĄD SQL (Pobieranie płatności): {e}")
    finally:
        if conn: conn.close()

    return upcoming, total_sum