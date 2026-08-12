import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta

NBP_URL = "https://api.nbp.pl/api/exchangerates/rates/a/{code}/{date}/?format=json"


def get_nbp_rate(currency_code: str, before_date: str, max_lookback_days: int = 7):
    """
    Kurs średni NBP (tabela A) z dnia poprzedzającego before_date (YYYY-MM-DD),
    zgodnie z zasadą podatkową. NBP nie publikuje w weekendy/święta, więc gdy
    dany dzień jest bez publikacji (404), cofamy się dzień po dniu.
    Zwraca (kurs, data_efektywna) albo (None, None) gdy nic nie znaleziono
    lub nie ma połączenia — wywołujący ma wtedy poprosić operatora o wpisanie
    kursu ręcznie.
    """
    try:
        base_date = datetime.strptime(before_date, "%Y-%m-%d") - timedelta(days=1)
    except (ValueError, TypeError):
        return None, None

    for i in range(max_lookback_days):
        day = base_date - timedelta(days=i)
        url = NBP_URL.format(code=currency_code, date=day.strftime("%Y-%m-%d"))
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())
                rate = data["rates"][0]
                return rate["mid"], rate["effectiveDate"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue  # brak publikacji tego dnia — cofamy się dalej
            return None, None
        except Exception:
            return None, None

    return None, None
