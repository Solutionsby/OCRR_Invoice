from datetime import datetime
import locale

# Próba ustawienia polskich nazw miesięcy
try:
    import platform
    if platform.system() == 'Windows':
        locale.setlocale(locale.LC_TIME, "Polish_Poland.1250")
    else:
        locale.setlocale(locale.LC_TIME, "pl_PL.UTF-8")
except:
    pass

def try_parse_date(raw_date: str) -> str:
    """Konwertuje dowolny format daty na YYYY-MM-DD."""
    if not raw_date or raw_date.lower() == "brak":
        return "brak"
    
    # Czyszczenie tekstu
    clean_date = raw_date.strip().replace("  ", " ")
    
    formats = [
        "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y",
        "%d %b %Y", "%d %B %Y", # 10 sty 2026, 10 stycznia 2026
        "%Y.%m.%d", "%y-%m-%d", "%d.%m.%y" # dodatkowe warianty
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(clean_date, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    return raw_date # Zwróć oryginał, jeśli nic nie pasuje