# OCR Invoice Parser

Aplikacja do OCR-owania faktur PDF, potwierdzania/korekty odczytanych danych przez operatora, segregowania plików do archiwum i zapisu do SQL Server — plus wysyłka mailowych przypomnień o nadchodzących płatnościach. Dwa sposoby pracy: **przeglądarka** (zalecane, `docker compose up`) albo **terminal** (`python run.py`) — oba używają dokładnie tej samej logiki (`core/`), więc zachowują się identycznie.

## 🔧 Technologie

- Python 3.9+ / Docker
- pytesseract + Tesseract OCR, pdf2image (+ poppler)
- SQL Server (pyodbc)
- FastAPI + statyczny frontend (bez builda — czysty HTML/CSS/JS)

## 🐳 Uruchomienie przez przeglądarkę (Docker)

```
docker compose up --build
```

Otwórz **http://localhost:8000**. Zakładki KSeF / Spoza KSeF / EURO odpowiadają
trzem przepływom opisanym niżej — lista faktur po lewej, podgląd PDF i
formularz korekty po prawej. Dodatkowo w pasku bocznym:

- 🔍 — wyszukiwanie faktury w SQL po numerze/kontrahencie (obie tabele)
- 📧 — link do osobnej podstrony **Mailer** (`/mailer.html`, patrz niżej) z
  przypomnieniami o płatnościach i raportami miesięcznymi
- ⚙️ — wybór, które foldery na dysku pełnią rolę źródła KSeF/inne/EURO i celu
  (patrz „Struktura folderów” niżej) — bez restartu kontenera

Operator jest automatycznie ostrzegany (czerwony baner), jeśli numer
otwieranej faktury już wcześniej trafił do bazy — chroni przed przypadkowym
przetworzeniem tej samej faktury dwa razy.

**Pierwsze uruchomienie na nowym komputerze:** upewnij się, że `.env` istnieje
(dane SQL/SMTP — nie jest w repo) i że komputer jest w tej samej sieci LAN co
serwer SQL. Jeśli foldery z fakturami mają leżeć gdzie indziej niż w katalogu
projektu, ustaw `HOST_DATA_DIR` w `.env` na szerszy folder nadrzędny przed
pierwszym `docker compose up` — konkretne podfoldery (KSeF/inne/EURO/cel)
wybiera się już z poziomu przeglądarki (⚙️), bez edycji configów.

## 🚀 Uruchomienie przez terminal (bez Dockera)

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

Logika odczytu/decyzji poniżej jest identyczna w obu trybach — różni się tylko
sposób interakcji: terminal pyta krok po kroku (`input()`), przeglądarka
pokazuje wszystkie pola w jednym formularzu na raz (z ostrzeżeniami zamiast
blokujących pytań, np. dla niejednoznacznego statusu płatności w KSeF).

### 1. KSeF (`main.py`)
Faktury mają ustandaryzowaną wizualizację KSeF, więc pola (sprzedawca, numer, daty, status/forma płatności, kwota brutto) są odczytywane po etykietach charakterystycznych dla tego layoutu (`extracters/extract_*.py`). Operator potwierdza/koryguje przez terminal (podgląd PDF otwiera się tylko przy korekcie lub gdy status płatności jest niejednoznaczny).

### 2. Spoza KSeF (`main_inne.py`)
Faktury o bardzo różnych, nieustandaryzowanych layoutach (zagraniczne agencje OTA, dostawcy) — kontrahent jest rozpoznawany po sufiksie formy prawnej (GmbH, B.V., LLC, S.A., Sp. z o.o., ...), a nie po etykiecie "Sprzedawca" (`extracters/inne/`). Podgląd PDF otwiera się od razu na starcie przetwarzania każdej faktury, bo odczyt jest tu mniej pewny niż w KSeF. Netto/VAT są odczytywane wprost, jeśli są jawnie podane — **brutto jest zawsze wyliczane jako netto+VAT, nigdy czytane wprost**. Gdy faktura nie pokazuje rozbicia netto/VAT (częste przy odwrotnym obciążeniu), program zakłada netto=kwota końcowa, VAT=0, i oznacza to w polu `source`, żeby było wiadomo, że to założenie a nie odczyt.

Dział i Kategoria (wymagane przez tabelę kosztową) są pobierane z `json/dzial_kategoria.json` po nazwie kontrahenta — przy nieznanej firmie program pyta raz i zapamiętuje na przyszłość.

### 3. Faktury EURO (`main_euro.py`)
Identyczny przepływ jak spoza KSeF, z dodatkowym krokiem przeliczenia EUR→PLN. Kurs jest domyślnie proponowany z NBP (tabela A, kurs z dnia **poprzedzającego** datę wystawienia — zgodnie z zasadą podatkową; NBP nie publikuje w weekendy/święta, więc program cofa się dzień po dniu aż znajdzie publikację). Operator akceptuje `[Enter]` albo wpisuje własny kurs — a gdy NBP nie odpowie (brak sieci), wpisanie kursu jest wymagane ręcznie. Oryginalne kwoty EUR i użyty kurs zostają zapisane w polu `Opis` jako ślad przeliczenia.

## 📁 Struktura folderów

Domyślnie (i tak jak dotychczas w CLI):

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

Te ścieżki nie są już zaszyte na sztywno — w przeglądarce (⚙️ w pasku bocznym)
można przypisać inne foldery jako źródło KSeF/inne/EURO i jako cel, bez
restartu. Zmiana zapisuje się w `settings.json: folders`; bez zapisanej
konfiguracji zachowanie jest identyczne jak powyżej. W Dockerze operator może
wybrać dowolny podfolder tego, co zamontowane pod `HOST_DATA_DIR` (patrz
sekcja o Dockerze wyżej).

## 🗄️ Baza danych (SQL Server)

- **`FAKTURY_KOSZTOWE`** — wszystkie faktury spoza KSeF / EURO (Numer, Kontrahent, Data, Netto, VAT, Dział, Kategoria, Opis, ...). Nie jest zapisywana z przepływu KSeF przez to narzędzie — koszty z KSeF trafiają tam zewnętrznym kanałem. Efektywnie to jedyna tabela z danymi kosztowymi dla wszystkich trzech rodzajów faktur naraz.
- **`Faktury_Kosztowe_Zmapowane`** (widok) — te same wiersze co `FAKTURY_KOSZTOWE`, plus kolumna `dzial_docelowy`: zmapowany, dużo krótszy zestaw działów (np. 9 zamiast ~20 surowych wartości `Dzial`). To z tego widoku (nie z surowej tabeli) budowany jest Excel w comiesięcznych raportach mailera (patrz niżej) — właśnie ten podział ma sens do raportowania.
- **`FAKTURY_DO_ZAPLATY`** — faktury nieopłacone z terminem płatności, z każdego z trzech przepływów; z tej tabeli korzysta `mail_sender.py` do wysyłki przypomnień.

## ⚙️ Konfiguracja

- `.env` — dane połączenia SQL (`DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_DRIVER`) i sekrety SMTP (`SENDER`, `EMAIL_PASSWORD`, `SMTP_SERVER`). Do Dockera dochodzi opcjonalnie `HOST_DATA_DIR` (patrz wyżej). **Plik zawiera prawdziwe dane produkcyjne — nie commitować.**
- `settings.json` — polityka mailera (`email_config.days_window`, `email_config.recipients`, `email_config.owner_recipients` — edytowalne z przeglądarki, zakładka „Ustawienia” na `/mailer.html`) i przypisania folderów (`folders` — edytowalne przez ⚙️). `EMAIL_RECIPIENTS` w `.env` jest już nieużywane — odbiorcy mailera żyją tylko tutaj.
- `patterns.json`, `json/knowledge_base.json` — nauczone aliasy nazw firm i kategorie (przepływ KSeF).
- `json/dzial_kategoria.json` — nauczona mapa firma → Dział/Kategoria (przepływy spoza KSeF / EURO).

## 📬 Mailer — osobna podstrona (`/mailer.html`)

Cała wysyłka (przypomnienia + wszystkie raporty) żyje na osobnej podstronie,
otwieranej z ikony 📧 w pasku bocznym głównej strony — nie w modalu, bo
liczba typów wysyłki zrobiła się zbyt duża na jeden popup. Sześć zakładek:

- **Przypomnienia** — podgląd, które faktury pasują do skonfigurowanego okna
  dni, możliwość odznaczenia pojedynczych przed wysyłką, historia wysyłek.
- **Pełna paczka** — patrz niżej.
- **Raport właściciela** — patrz niżej.
- **Wg działu** / **Wg kontrahenta** — patrz niżej.
- **Ustawienia** — jedno miejsce edycji `email_config.days_window`,
  `recipients` i `owner_recipients`; pozostałe zakładki tylko z nich
  korzystają (poza „Wg działu”/„Wg kontrahenta”, gdzie odbiorców wpisuje się
  ręcznie przy każdej wysyłce).

Z terminala (np. cron), bez zmian — to osobny, dużo prostszy skrypt,
niezależny od podstrony:

```
python mail_sender.py
```
Wysyła maile o fakturach z `FAKTURY_DO_ZAPLATY` z terminem płatności w skonfigurowanym oknie dni (domyślnie ±7), dołączając PDF-y, i po wysyłce przenosi opłacone faktury do archiwum `<MM>/<Firma>`.

Wysyłka wszystkich faktur, które nie zostały wysłane: `python mail_sender.py --all`

## 📦 Raporty miesięczne

Cztery osobne, ręcznie wyzwalane wysyłki (zakładki na `/mailer.html`) — każda
z własnym wyborem miesiąca i podglądem przed wysłaniem.

**Pełna paczka (księgowość)** — jeden mail z:
- **wszystkimi PDF-ami** faktur z tego miesiąca — zarówno już zarchiwizowane
  (`<MM>/<Firma>`), jak i te, które wciąż czekają na zapłatę w `do_zaplaty` i
  nie przeszły jeszcze przez cotygodniowy mailer przypomnień,
- **arkuszem Excel** z podsumowaniem (Firma, Nr faktury, Data wystawienia,
  Netto, VAT, Brutto + wiersz SUMA) — **tylko dla pozycji, które faktycznie
  mają załączony PDF.**

To ostatnie jest celowe, nie oczywiste: `FAKTURY_KOSZTOWE`/widok
`Faktury_Kosztowe_Zmapowane` zawiera więcej wierszy niż to narzędzie
kiedykolwiek widziało jako plik na dysku — KSeF trafia tam też zewnętrznym
kanałem, niezależnym od PDF-ów przetworzonych tutaj. Bez filtrowania Excel
pokazywałby więc pozycje bez żadnego załącznika. Dopasowanie: numer faktury z
bazy jest sanityzowany tą samą regułą co przy zmianie nazwy pliku
(`file_renamer.sanitize_invoice_number`) i sprawdzany, czy pasuje do nazwy
któregoś ze znalezionych PDF-ów. Odbiorcy: `email_config.recipients` (ta sama
lista co przypomnienia o płatnościach).

**Raport właściciela** — jeden mail, **sam Excel, bez PDF-ów**:
- treść maila to krótkie podsumowanie z podziałem na Dział (liczba faktur i
  suma brutto na dział),
- Excel ma dodatkową kolumnę „Dział” i, w odróżnieniu od pełnej paczki,
  **obejmuje wszystkie pozycje za dany miesiąc, niezależnie od tego, czy jest
  do nich załączony PDF** — to raport zarządczy „ile wydaliśmy i na co”, nie
  komplet dokumentów księgowych.
- Dział pochodzi z kolumny `dzial_docelowy` widoku `Faktury_Kosztowe_Zmapowane`
  — zmapowany, krótszy zestaw działów (np. 9) niż surowa kolumna `Dzial` w
  `FAKTURY_KOSZTOWE` (potrafi mieć ~20 rozdrobnionych wartości typu „RDS
  DRUK”/„KI DRUK”).
- Odbiorcy: osobna lista `email_config.owner_recipients`, edytowalna w
  zakładce „Ustawienia”.

**Raport wg działu** / **Raport wg kontrahenta** — jeden mail, przefiltrowany
do jednego działu (z listy `dzial_docelowy`) albo jednego kontrahenta (z
listy firm widocznych w wybranym oknie). W odróżnieniu od pozostałych dwóch
raportów mają dwie własne opcje:

- **okno „Od”–„Do”**, nie pojedynczy miesiąc — obejmuje dowolną liczbę
  miesięcy i lat (np. cały kwartał, albo przełom grudnia/stycznia); wybór
  tego samego miesiąca w obu polach daje efekt identyczny jak dawny
  pojedynczy selector,
- **przełącznik „Dołącz PDF-y”**: włączony (domyślnie) — ten sam wzór co
  pełna paczka księgowa, Excel i załączniki ograniczone do wierszy
  faktycznie mających PDF w wybranym oknie; wyłączony — sam Excel, bez
  załączników, ale wtedy obejmuje **wszystkie** pozycje działu/kontrahenta w
  oknie, niezależnie od tego, czy mają PDF (jak raport właściciela — bez
  załącznika nie ma powodu ukrywać wierszy bez pliku).

Odbiorców wpisuje się ręcznie przy każdej wysyłce (bez zapisanej mapy
dział/kontrahent → odbiorcy).

Wszystkie cztery wysyłki są wyłącznie informacyjne: w odróżnieniu od mailera
przypomnień **nie przenoszą plików ani nie zmieniają niczego w SQL** (nie
oznaczają jako wysłane, nie archiwizują) — można je wysłać wielokrotnie bez
efektów ubocznych dla stanu płatności.

API: `GET /api/mailer/monthly/preview|owner-preview` (pełna paczka/właściciel,
`year=`/`month=`), `GET /api/mailer/monthly/dzial-preview|kontrahent-preview`
(`year_from=&month_from=&year_to=&month_to=&dzial=|kontrahent=&with_pdfs=`),
`POST /api/mailer/monthly/send|owner-send` (`{"year":...,"month":...}`),
`POST /api/mailer/monthly/dzial-send|kontrahent-send`
(`{"year_from":...,"month_from":...,"year_to":...,"month_to":...,"dzial"|"kontrahent":...,"recipients":[...],"with_pdfs":true|false}`),
`GET /api/mailer/monthly/dzialy|kontrahenci` (`year_from=&month_from=&year_to=&month_to=`
— listy do selectów w UI).