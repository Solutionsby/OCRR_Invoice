import re

# Faktury spoza KSeF (agencje OTA, zagraniczni dostawcy) nie mają jednego
# stałego layoutu — etykiety kwot są po polsku i po angielsku, więc dla
# każdej wartości sprawdzamy listę wariantów w kolejności priorytetu.
NET_LABELS = [
    r"Warto[sś][cć]\s*Netto\s*razem",
    r"Subtotal\s*Before\s*Tax",
    r"Kwota\s*netto",
    r"Netto\s*razem",
    r"Suma\s*netto",
    r"Warto[sś][cć]\s*netto",
]
VAT_LABELS = [
    r"Warto[sś][cć]\s*Vat",
    r"VAT\s*\(%\)",
    r"Kwota\s*VAT",
    r"Podatek\s*VAT",
    r"Mwst\.?",
]
TOTAL_LABELS = [
    r"Razem\s*do\s*zap[łl]aty",
    r"Total\s*Amount\s*Due",
    r"Ca[łl]kowita\s*kwota\s*do\s*zap[łl]aty",
    r"Kwota\s*łączna",
    r"Do\s*zap[łl]aty",
    r"Kwota\s*nale[żz]no[śs]ci\s*ogó[łl]em",
    r"Gesamtsumme",
    r"Gesamtbetrag",
]

# Kwota po etykiecie: opcjonalny dwukropek/spacje, opcjonalna waluta przed
# liczbą (np. "PLN 170.36"), sama liczba (dopuszcza spację/kropkę/przecinek
# jako separator tysięcy/dziesiętny, i minus dla not credytowych).
_AMOUNT_AFTER = r"[:\s]*(?:PLN|USD|EUR)?\s*(-?[\d][\d\s.,]*\d)"

# Ostatnia szansa, gdy kolumna kwot totalnych jest całkiem oddzielona od
# etykiet przez OCR (dwukolumnowy layout rozjechany wierszami — np. Aurena
# przy dłuższych listach pozycji): token w stylu "123,45"/"0,00" zawsze z
# przecinkiem jako separatorem dziesiętnym (2 cyfry), co odróżnia go od IBAN,
# dat i innych ciągów cyfr. Wartości totalne (Zuschlagssumme, VAT, opłata,
# VAT, Gesamtsumme) trafiają w tekście w tej kolejności, więc ostatni taki
# token w całym dokumencie to suma końcowa.
_MONEY_TOKEN_RE = re.compile(r"-?\d[\d\s.]*,\d{2}")


def parse_number(raw: str) -> float:
    """Normalizuje zapis liczby PL/EN ('2.021,88' albo '170.36') do float."""
    s = raw.strip().replace(" ", "")
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        value = float(s)
    except ValueError:
        return 0.0
    return -value if neg else value


def _find_amount(text: str, labels):
    for label in labels:
        match = re.search(label + _AMOUNT_AFTER, text, re.IGNORECASE)
        if match:
            return parse_number(match.group(1)), label
    return None, None


def extract_amounts(text: str) -> dict:
    """
    Zwraca netto/vat/brutto. Brutto zawsze wyliczane jako netto+vat (nie
    czytane wprost), zgodnie z założeniem: dla faktur spoza KSeF ufamy
    tylko netto i VAT jako źródłu.

    Gdy na fakturze nie ma osobnej etykiety netto/VAT (częste dla zagranicznych
    faktur prowizyjnych objętych odwrotnym obciążeniem VAT), a jest tylko
    kwota końcowa ("Do zapłaty"/"Total Amount Due"...), zakładamy netto=ta
    kwota i vat=0 — `source` w zwróconym słowniku informuje, że to założenie,
    a nie odczyt wprost, żeby operator mógł to zweryfikować.
    """
    netto, netto_label = _find_amount(text, NET_LABELS)
    vat, vat_label = _find_amount(text, VAT_LABELS)
    total, total_label = _find_amount(text, TOTAL_LABELS)

    if netto is not None and vat is not None:
        brutto = round(netto + vat, 2)
        source = "netto_i_vat_odczytane"
    elif total is not None:
        netto, vat, brutto = total, 0.0, total
        source = "fallback_total_jako_netto_vat_0"
    else:
        fallback_tokens = _MONEY_TOKEN_RE.findall(text)
        if fallback_tokens:
            last_amount = parse_number(fallback_tokens[-1])
            netto, vat, brutto = last_amount, 0.0, last_amount
            source = "fallback_ostatnia_kwota_w_tekscie"
        else:
            netto, vat, brutto = 0.0, 0.0, 0.0
            source = "brak_kwot"

    return {
        "netto": netto,
        "vat": vat,
        "brutto": brutto,
        "source": source,
        "netto_label": netto_label,
        "vat_label": vat_label,
        "total_found": total,
        "total_label": total_label,
    }
