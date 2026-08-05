import re
from datetime import datetime

def extract_payment_status(text: str) -> str:
    """
    Odczytuje pole 'Informacja o płatności' z wizualizacji KSeF (np. 'Brak
    zapłaty'). Zwraca dosłowne "brak" tylko gdy tej etykiety w ogóle nie ma
    na fakturze (część layoutów KSeF jej nie pokazuje) — to odróżnia
    "pole nieobecne" od realnego statusu "Brak zapłaty".
    """
    match = re.search(r"Informacja o płatności:\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else "brak"

def extract_payment_form(text: str) -> str:
    """Odczytuje pole 'Forma płatności' z wizualizacji KSeF (np. 'Przelew')."""
    match = re.search(r"Forma płatności:\s*(.+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else "brak"

def is_paid(payment_status: str) -> bool:
    """Fakturę uznajemy za opłaconą tylko gdy status wprost o tym mówi (nie zawiera 'brak')."""
    status = (payment_status or "").lower()
    return "zapłac" in status and "brak" not in status

def status_is_missing(payment_status: str) -> bool:
    """True tylko gdy etykiety 'Informacja o płatności' w ogóle nie było na fakturze."""
    return payment_status == "brak"

def assume_paid_via_cod_heuristic(payment_form: str) -> bool:
    """
    Płatność "Pobranie" oznacza zapłatę w momencie dostawy — jeśli KSeF nie
    podaje wprost statusu, zakładamy że taka faktura jest już opłacona.
    """
    return "pobranie" in (payment_form or "").strip().lower()

def assume_unpaid_via_transfer_heuristic(payment_form: str, invoice_date: str, pay_date: str) -> bool:
    """
    Gdy KSeF nie podaje wprost "Informacja o płatności": jeśli forma płatności
    to przelew (dopuszczamy też warianty typu "Inna - Przelew"), a termin
    płatności jest późniejszy niż data wystawienia, prawie na pewno faktura
    jeszcze nie jest opłacona (typowy wzorzec faktury kosztowej czekającej na
    przelew z odroczonym terminem) — nie trzeba wtedy pytać operatora.
    W pozostałych przypadkach (forma płatności bez "przelew" w treści, brak
    dat, albo termin nie jest późniejszy niż wystawienie) zwraca False, co
    oznacza "nie da się jednoznacznie wywnioskować".
    """
    if "przelew" not in (payment_form or "").strip().lower():
        return False
    try:
        d_inv = datetime.strptime(invoice_date, "%Y-%m-%d")
        d_pay = datetime.strptime(pay_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    return d_pay > d_inv
