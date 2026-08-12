# OCR Invoice Parser

Lokalna aplikacja CLI do OCR-owania faktur PDF, interaktywnego potwierdzania/korekty odczytanych danych przez operatora, segregowania plików do archiwum i zapisu do SQL Server — plus wysyłka mailowych przypomnień o nadchodzących płatnościach.

## 🔧 Technologie

- Python 3.9+
- pytesseract + Tesseract OCR, pdf2image (+ poppler)
- SQL Server (pyodbc)
- pdf2image / Pillow

## 🚀 Jak uruchomić

```
python run.py
```

`run.py` pyta, które faktury chcesz wprowadzić, i odpala odpowiedni moduł:

| Wybór | Moduł | Folder źródłowy | Kiedy używać |
|---|---|---|---|
| `[1]` | `main.py` | `faktury_surowe/` | Faktury z wizualizacji KSeF (polski dostawca, PLN) |
| `[2]` | `main_inne.py` | `faktury_surowe/inne/` | Faktury w PLN spoza KSeF (zagraniczne OTA, dostawcy) |
| `[3]` | `main_euro.py` | `faktury_surowe/euro/` | Faktury w EUR — przeliczane na PLN |

Każdy moduł można też odpalić samodzielnie, np. `python main_inne.py`.

## 📄 Trzy przepływy

### 1. KSeF (`main.py`)
Faktury mają ustandaryzowaną wizualizację KSeF, więc pola (sprzedawca, numer, daty, status/forma płatności, kwota brutto) są odczytywane po etykietach charakterystycznych dla tego layoutu (`extracters/extract_*.py`). Operator potwierdza/koryguje przez terminal (podgląd PDF otwiera się tylko przy korekcie lub gdy status płatności jest niejednoznaczny).

### 2. Spoza KSeF (`main_inne.py`)
Faktury o bardzo różnych, nieustandaryzowanych layoutach (zagraniczne agencje OTA, dostawcy) — kontrahent jest rozpoznawany po sufiksie formy prawnej (GmbH, B.V., LLC, S.A., Sp. z o.o., ...), a nie po etykiecie "Sprzedawca" (`extracters/inne/`). Podgląd PDF otwiera się od razu na starcie przetwarzania każdej faktury, bo odczyt jest tu mniej pewny niż w KSeF. Netto/VAT są odczytywane wprost, jeśli są jawnie podane — **brutto jest zawsze wyliczane jako netto+VAT, nigdy czytane wprost**. Gdy faktura nie pokazuje rozbicia netto/VAT (częste przy odwrotnym obciążeniu), program zakłada netto=kwota końcowa, VAT=0, i oznacza to w polu `source`, żeby było wiadomo, że to założenie a nie odczyt.

Dział i Kategoria (wymagane przez tabelę kosztową) są pobierane z `json/dzial_kategoria.json` po nazwie kontrahenta — przy nieznanej firmie program pyta raz i zapamiętuje na przyszłość.

### 3. Faktury EURO (`main_euro.py`)
Identyczny przepływ jak spoza KSeF, z dodatkowym krokiem przeliczenia EUR→PLN. Kurs jest domyślnie proponowany z NBP (tabela A, kurs z dnia **poprzedzającego** datę wystawienia — zgodnie z zasadą podatkową; NBP nie publikuje w weekendy/święta, więc program cofa się dzień po dniu aż znajdzie publikację). Operator akceptuje `[Enter]` albo wpisuje własny kurs — a gdy NBP nie odpowie (brak sieci), wpisanie kursu jest wymagane ręcznie. Oryginalne kwoty EUR i użyty kurs zostają zapisane w polu `Opis` jako ślad przeliczenia.

## 📁 Struktura folderów

```
faktury_surowe/            # wejście: PDF-y czekające na przetworzenie
├── inne/                  # faktury spoza KSeF (PLN)
└── euro/                  # faktury w EUR

faktury_przetworzone/       # wyjście: pliki po zmianie nazwy i segregacji
├── <MM>/<Firma>/           # archiwum opłaconych faktur, po miesiącu wystawienia
└── do_zaplaty/              # nieopłacone, czekają na mailer
    └── do_wpisania_recznie/
```

Pliki są przenoszone tylko po zmianie nazwy na schemat `MM_YYYY_FV_Numer_Firma.pdf`.

## 🗄️ Baza danych (SQL Server)

- **`FAKTURY_KOSZTOWE`** — wszystkie faktury spoza KSeF / EURO (Numer, Kontrahent, Data, Netto, VAT, Dział, Kategoria, Opis, ...). Nie jest zapisywana z przepływu KSeF (koszty z KSeF trafiają do bazy innym kanałem).
- **`FAKTURY_DO_ZAPLATY`** — faktury nieopłacone z terminem płatności, z każdego z trzech przepływów; z tej tabeli korzysta `mail_sender.py` do wysyłki przypomnień.

## ⚙️ Konfiguracja

- `.env` — dane połączenia SQL (`DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) i SMTP (`SENDER`, `EMAIL_PASSWORD`, `SMTP_SERVER`, `EMAIL_RECIPIENTS`). **Plik zawiera prawdziwe dane produkcyjne — nie commitować.**
- `settings.json` — odbiorca/mailer.
- `patterns.json`, `json/knowledge_base.json` — nauczone aliasy nazw firm i kategorie (przepływ KSeF).
- `json/dzial_kategoria.json` — nauczona mapa firma → Dział/Kategoria (przepływy spoza KSeF / EURO).

## 📬 Mailer przypomnień o płatnościach

```
python mail_sender.py
```
Wysyła maile o fakturach z `FAKTURY_DO_ZAPLATY` z terminem płatności w oknie ±7 dni, dołączając PDF-y, i po wysyłce przenosi opłacone faktury do archiwum `<MM>/<Firma>`.


Wysyłka wszystich faktur ktore nie zostaly wyslane - python mail_sender.py --all