# Plan: Analityka (branch `analityka`, zmergowany do `main`)

Roboczy plik z etapami. Szczegóły poszczególnych poprawek (bugi, dokładne
zapytania SQL, uzasadnienia) są w historii commitów — tu tylko stan i to, co
dalej.

## Zrobione ✅

**Dashboard `/analityka.html`** (`core/analytics.py`, `api/routers/analytics.py`,
`utils/database_manager.py`, `frontend/analityka.{html,js}`), 5 zakładek na
widoku `Faktury_Kosztowe_Zmapowane`:

- **Trend** — miesięczny trend kosztów (netto/VAT/brutto), filtr
  wszystkie/cykliczne/jednorazowe (`CzyCykliczna` z `dbo.KONTRAHENCI_CYKLICZNI`,
  55 kontrahentów oznaczonych), prosty baseline prognozy (mediana + wskaźnik
  sezonowości — jawnie NIE model ML, patrz uzasadnienie w rozmowie
  2026-08-20/21) z tym samym filtrem.
- **Kontrahenci** — ranking TOP N wg brutto, filtr działu.
- **Działy** — struktura kosztów wg `dzial_docelowy` w czasie (stacked bar).
- **Kategorie** — 155 surowych wartości KATEGORIA scalone do 143 (normalizacja
  polskich znaków/literówek, `core/analytics._merge_variants`), drill-down do
  podkategorii, filtr działu.
- **Dochód** — koszt netto vs. przychód netto (`Przychody.dbo.Przychod_Netto`,
  cross-database query) per dział. Karta „Brandy łącznie" + 6 kart per brand
  (CornerMarket, Hotel, RDS, Gastronomia, Automaty, Wspólne), posortowane od
  najlepszego do najgorszego dochodu. Brak śledzonego przychodu = 0 zł (dochód
  = −koszt), wszystkie działy wchodzą do sum. „Pozostałe działy" (koszty
  wsparcia/ogólne, nigdy nie będą miały przychodu) — sama tabela Dział/Koszt,
  posortowana malejąco, z sumą.

**Kluczowe fakty o danych, które trzeba pamiętać:**
- Rzetelna, ciągła historia kosztów zaczyna się dopiero **2024-01** (wcześniej
  pojedyncze, odosobnione wpisy z 2018/2023) — stąd domyślne zakresy „Od" w UI
  i ostrzeżenia przy cofaniu zakresu wcześniej.
- Login SQL aplikacji (`DB_USER`/`PYTHON`) ma dziś `SELECT` na `Faktury`,
  `Przychody` i bazach źródłowych `Przychod_Netto` odpytuje (w tym „Sopocki
  Zdroj") — każda NOWA baza źródłowa przychodu będzie wymagać dodania
  uprawnień po stronie użytkownika (SSMS), inaczej cross-database query padnie
  `permission denied`.
- `KONTRAHENCI_CYKLICZNI` i `Przychod_Netto` to tabele/widoki zarządzane przez
  użytkownika w SSMS — brak migracji w tym repo, żadnych zmian schematu nie
  robimy stąd bezpośrednio (apka nie ma nawet `VIEW DEFINITION` na
  `Faktury_Kosztowe_Zmapowane`).

Wszystko zcommitowane i wypchnięte na `origin/main` (ostatni commit: `288ac4e`).

**Gałąź `Przychod`** (2026-08-24, od `main`@`288ac4e`) — 6. zakładka **„Trend wg
działu"**: jeden dział na raz (dropdown, te same 6 brandów co w Dochodzie),
wykres Przychód netto i osobno Dochód netto, miesiąc (Sty-Gru) na osi X, jedna
linia na rok — porównanie np. czerwca 2024 vs 2025 vs 2026.
`core.analytics.get_dochod_trend(dzial, ...)` (pivotuje płaskie wiersze
`db.get_dochod(..., dzial=X)` w serie per rok), `GET /api/analytics/dochod-trend`.
Domyślny zakres „Od" = 2015-01 (szeroki, nie 2024-01 jak w zakładce Dochód) —
przychód, w odróżnieniu od kosztu, NIE jest ograniczony niekompletnością
sprzed 2024 (dla Hotelu przychód sięga 2019). Ostrzeżenie o niekompletnym
koszcie zostaje TYLKO przy wykresie Dochodu, nie Przychodu. Zweryfikowane na
żywych danych: Hotel ma przychód od 2018/2019 do dziś, dochód dla lat
2019-2023 wychodzi ≈ przychodowi (bo koszt w bazie za te lata jest prawie
zerowy — zgodne z wiedzą o niekompletnych danych, nie błąd). Słupki dla lat
przeszłych + linia dla bieżącego roku (na życzenie użytkownika, mixed
bar+line w Chart.js).

Doszła **prognoza przychodu i dochodu per dział** — ten sam baseline (mediana
+ sezonowość) co dla kosztów, wydzielony do współdzielonego rdzenia
`core.analytics._median_seasonal_forecast(points, value_field, months_ahead)`
(używany teraz przez `get_spend_forecast` I `get_dochod_forecast`).
`get_dochod_forecast(dzial, months_ahead)` liczy przychód i dochód osobno —
przychód pomija miesiące bez śledzonych danych (nie liczy ich jako 0, żeby
nie zaniżać sezonowości), dochód liczy brak przychodu jako 0 (spójnie z
resztą Dochodu). `GET /api/analytics/dochod-forecast?dzial=X&months_ahead=N`.
Na wykresie: kropkowana prognoza doklejona do linii bieżącego roku (nie
tworzy osobnej serii na kolejny rok — prognoza wykraczająca poza grudzień
bieżącego roku jest po prostu pomijana, celowe uproszczenie). Zweryfikowane
na żywych danych: Hotel 44 mies. historii przychodu, RDS/Gastronomia 30,
Wspólne 24, Automaty 19 (przychód) / 31 (dochód, bo koszt sięga dalej niż
śledzony przychód).

Jeszcze na tej samej gałęzi doszły 3 rzeczy (na pytanie „co jeszcze możemy
przygotować"):
- **Marża %** (`dochod/przychod × 100`) — pole `marza_pct` w każdym
  `DochodItem` + `total_marza_pct`, karty w zakładce Dochód mają teraz linię
  „Marża". Pozwala porównać rentowność działów o różnej skali (Hotel 89,6%
  vs Automaty 4,2% — w złotówkach nieporównywalne, w % owszem).
- **Wynik całej firmy (suma 6 brandów) z prognozą** — nowa opcja
  „— Wszystkie brandy (suma) —" w dropdownie działu na zakładce „Trend wg
  działu". `core.analytics.get_dochod_trend_total`/`get_dochod_forecast_total`
  (nowy helper `_sum_dochod_rows` sumuje wiersze z `db.get_dochod()` po liście
  działów), `GET /api/analytics/dochod-trend-total?dzialy=A,B,C&...` i
  `/dochod-forecast-total`. Lista działów przekazywana z frontu
  (`DOCHOD_NAMED_DZIALY.join(",")`), nie zaszyta w backendzie.
- **Kategorie z filtrem cykliczne/jednorazowe** — `CzyCykliczna` dociągnięty
  do `get_kategoria_breakdown`/`get_podkategoria_breakdown` (dropdown „Rodzaj
  kosztów" na zakładce Kategorie, ten sam wzorzec co na Trend/Kontrahenci).

Uwaga wydajnościowa: pierwsze zapytanie cross-database (do `Przychody`) po
starcie procesu bywa wolne (~60s w teście), kolejne już szybkie (~5s) —
prawdopodobnie koszt nawiązania połączenia z serwerem źródłowym, nie błąd.

Doszła też **zakładka „Przegląd"** — nowa PIERWSZA/domyślna zakładka,
dashboard z 6 kartami, celowo BEZ nowych endpointów (tylko `Promise.all` nad
istniejącymi: `/dochod`, `/trend`, `/dochod-forecast-total`):
1. Ten miesiąc — cała firma (przychód/koszt/dochód/marża, suma 6 brandów)
2. Prognoza na najbliższy miesiąc (cała firma)
3. Koszty — zmiana miesiąc do miesiąca (kwota + %, strzałka)
4. Cykliczne vs jednorazowe (% udziału, rok bieżący od stycznia)
5. Ranking brandów wg dochodu (rok bieżący od stycznia)
6. Uwagi (dynamicznie: działy bez śledzonego przychodu)

Pułapka znaleziona przy weryfikacji na żywych danych: dla bieżącego miesiąca
przychód bywa już kompletny (wpisywany zbiorczo), a koszt wciąż napływa (OCR
faktur trwa) — dochód „tego miesiąca" może wyglądać sztucznie dobrze, dopóki
miesiąc się nie zamknie księgowo. Naprawione: stałe zastrzeżenie przy karcie 1
(nie warunkowe po dniu miesiąca — próbowałem tego, ale niekompletność kosztu
zdarza się nawet w pełni zakończonych miesiącach, patrz lipiec 2026 wcześniej
w tej rozmowie).

Wdrożone do Dockera. **Nie zcommitowane jeszcze.**

**Optymalizacja wydajności** (2026-08-24, na zgłoszenie "wszystko lekko
spowalnia", pytanie o Redis): sprawdziłem — to NIE problem ilości danych
(`FAKTURY_KOSZTOWE` 3609 wierszy, `Przychod_Netto` 184 — trywialne dla SQL
Servera), więc Redis byłby złym narzędziem (rozwiązuje cache współdzielony
między instancjami/drogie obliczenia — nie mamy ani jednego, ani drugiego).
Prawdziwa przyczyna: `frontend/analityka.js` ładował WSZYSTKIE 7 zakładek
(Przegląd sam w sobie robi 6 zapytań) równolegle przy każdym otwarciu strony
— kilkanaście zapytań do bazy naraz, część cross-database do `Przychody`
(te bywały wolne przy "rozgrzewaniu" — patrz notatka wyżej). Naprawione:
**leniwe ładowanie zakładek** — `TAB_LOADERS` (mapa zakładka→funkcja
ładująca) + `loadedTabs` (Set), spięte z istniejącym listenerem przełączania
zakładek; dana zakładka ładuje się dopiero przy PIERWSZYM kliknięciu, potem
zostaje w pamięci (kolejne kliknięcia nie odpytują bazy ponownie — tylko
przycisk „Odśwież” robi to świadomie). Start strony robi teraz tylko
`loadPrzeglad()` (bo to domyślna aktywna zakładka) zamiast 7 równoległych
wywołań. Wdrożone do Dockera.

Leniwe ładowanie NIE wystarczyło — użytkownik zgłosił, że nadal wolno, a po
próbie zmierzenia okazało się gorzej: **żywy connection reset (10054)** przy
zwykłym użyciu, nie tylko subiektywne spowolnienie. Zdiagnozowane i
naprawione właściwie (`utils/database_manager.py`, `api/main.py`):

- **Jedno trwałe połączenie SQL na cały czas życia procesu** zamiast
  otwierania nowego w każdej z 14 funkcji (`_SharedConnectionHandle`,
  `_shared_conn` moduł-level). Zmierzone: pierwsze `pyodbc.connect()` >100s,
  pierwszy dostęp cross-database do `Przychody` na TYM połączeniu kolejne
  >30s — ale KOLEJNE zapytania na tym samym połączeniu: 0,06–5s. Dawny
  wzorzec (open/close per zapytanie) płacił ten koszt praktycznie za każdym
  razem, bo sesja nigdy nie była "rozgrzana" dłużej niż jedno zapytanie.
- **Lock (`_conn_lock`)** serializujący dostęp — pyodbc.Connection nie jest
  bezpieczne przy równoległym użyciu z wielu wątków (FastAPI odpala sync
  endpointy w threadpoolu); to też naprawiło żywy crash: dwa jednoczesne
  zapytania cross-database (np. karty Przeglądu przez `Promise.all`) dawały
  connection reset. Przy okazji naprawione też we `frontend/analityka.js` —
  `loadPrzeglad()` odpytuje zapytania dotykające Przychody PO KOLEI, nie
  równolegle (zapytania czysto kosztowe zostały w `Promise.all`).
- **`_RetryingCursor`** — `.execute()` łapie zerwane połączenie DOKŁADNIE
  tam, gdzie występuje (nie osobnym prefetch-checkiem `SELECT 1`, który nie
  łapał realnego przypadku — sesja cross-database potrafi wygasnąć
  niezależnie od żywotności bazowego połączenia), łączy się ponownie i
  ponawia to samo zapytanie raz.
- **Rozgrzewanie przy starcie kontenera** (`api/main.py`, wątek-daemon w
  `@app.on_event("startup")`) — pierwszy prawdziwy użytkownik po restarcie
  nie płaci już kosztu nawiązania połączenia; `/health` odpowiada od razu
  (rozgrzewanie nie blokuje startu serwera).
- **Heartbeat co 30s** (`db.start_keepalive()`) — kluczowe odkrycie: reset
  występował NAWET na zwykłych zapytaniach niedotykających Przychody (np.
  `/api/mailer/monthly/dzialy`), więc to nie problem cross-database, tylko
  zwykły timeout bezczynnego połączenia (Docker NAT / firewall / sam SQL
  Server ubija sesję stojącą bezczynnie zbyt długo — dokładna przyczyna poza
  zasięgiem aplikacji, nie do zdiagnozowania stąd). Heartbeat nie dopuszcza
  do bezczynności długiej na tyle, by to nastąpiło; jeśli mimo to złapie
  reset, naprawia się cicho w tle, zanim realne zapytanie użytkownika do
  niego dotrze. Zweryfikowane na żywo: zapytanie po symulowanej 90s przerwie
  w ruchu — 1,45s (log pokazał, że heartbeat złapał i naprawił reset w tle
  chwilę wcześniej, użytkownik tego nie widział).

ODBC connection string dostał też `ConnectRetryCount=3;ConnectRetryInterval=5`
(sterownik sam próbuje ponownie przy pewnych transient errorach, zanim
w ogóle dojdzie do naszego retry na cursorze).

**Poprawka #2 tego samego dnia** — użytkownik zgłosił, że mimo powyższego
nadal "cały czas się coś wywala": w logach ~20-40 komunikatów "⚠️ Zapytanie
SQL padło" pod rząd w niecałą sekundę, BEZ ani jednego sukcesu pomiędzy
nimi (wcześniej: 1 komunikat = 1 natychmiastowy sukces). Zdiagnozowane:
sterownik ODBC ma WŁASNĄ, wewnętrzną pulę połączeń (domyślnie włączoną) —
`_connect_fresh()` po zerwanym połączeniu dostawał z tej puli KOLEJNE martwe
połączenie zamiast prawdziwie nowego, więc każda próba naprawy natychmiast
padała ponownie, tworząc kaskadę. Naprawione: `pyodbc.pooling = False` na
starcie modułu (i tak zarządzamy jednym trwałym połączeniem sami —
`_shared_conn` — pula sterownika była zbędna i szkodliwa) + jawne
`_shared_conn.close()` starego połączenia przed reconnectem (nie liczyć na
GC). Zweryfikowane: odtworzenie dokładnie tego samego scenariusza (seria
równoległych zapytań jak przy realnym otwarciu strony) po tej poprawce dała
tylko 2 pojedyncze ostrzeżenia, każde z natychmiastowym sukcesem — zero
kaskady.

Wdrożone do Dockera. **Nie zcommitowane jeszcze.**

**Poprawka #3** — po poprawce #2 apka zawiesiła się CAŁKOWICIE na >12 minut
(WSZYSTKIE zapytania do bazy, nawet zwykłe, bez żadnego logu błędu — 60s+
curl bez odpowiedzi). Przyczyna: ani `pyodbc.connect()`, ani wykonanie
zapytania nie miały jawnego timeoutu — jeśli sieć nie odpowiada (zamiast
zwrócić szybki błąd), pyodbc/ODBC potrafi czekać W NIESKOŃCZONOŚĆ, trzymając
`_conn_lock` zablokowany na zawsze (żadne kolejne zapytanie nigdy go nie
dostanie). Naprawione: `pyodbc.connect(..., timeout=180)` +
`conn.timeout = 90` (limit na wykonanie KAŻDEGO zapytania) — teraz "wisi bez
końca" zawsze zamienia się w rzucony wyjątek, który `_RetryingCursor` już
umie złapać i naprawić, zamiast permanentnie blokować całą aplikację.
Wymagało ręcznego `docker compose restart` do przywrócenia działania (lock
raz zawieszony na stałe nie naprawia się sam — to jedyny scenariusz, w
którym trzeba ręcznie zrestartować kontener).

Przy okazji: domyślny zakres „Trend wg działu" skrócony z 2015 na 2025 (na
życzenie użytkownika, mniej danych = mniejsze obciążenie), i dodana
**tabela trafności prognozy (backtest)** w tej samej zakładce —
`core.analytics._backtest_forecast` liczy, co baseline przewidziałby dla
każdego z ostatnich N miesięcy, używając WYŁĄCZNIE danych sprzed niego
(walk-forward, bez podglądania przyszłości), zestawione z tym, co faktycznie
wyszło. `GET /api/analytics/{forecast-backtest,dochod-backtest,
dochod-backtest-total}`. Powód: użytkownik nie miał jak ocenić, czy model
miał rację dla miesięcy, które już mamy w danych — teraz jest to wprost
widoczne w tabeli (Hotel: blisko w lipcu +3,4%, wyraźnie zaniżał
kwiecień-czerwiec +27% do +51%).

## Etap: zakładka Hotel (MongoDB) — 2026-08-25 ✅

Nowe źródło danych: `MONGO_URI` w `.env` → baza `priceOptimizer`, kolekcja
`incomes` (paragony/faktury/anulacje/korekty systemu hotelowego, 4801 dok.,
2026-01 do dziś). Osobna technologia (MongoDB, nie SQL Server) — `pymongo`
dodany do `requirements.txt`, nowy moduł `utils/mongo_manager.py`
(pojedynczy `MongoClient`, bezpieczny wielowątkowo out-of-the-box — bez
locków/heartbeatów jak dla pyodbc) + `core/hotel_analytics.py`.

- Nazwy pozycji sprzedaży (`nazwa`) mają te same problemy co KATEGORIA w SQL
  (literówki, dopiski w nawiasach) — `_normalize_product_name` scala 65→43
  pozycje: trailing kropka, nawiasowy dopisek (status/referencja), i
  wszystkie warianty „Zadatek ..." (mają osadzone daty pobytu, unikalne per
  rezerwacja) pod jedną etykietę.
- Anulacje/korekty mają już ujemne kwoty w źródle — zwykłe SUM daje poprawny
  wynik netto, bez potrzeby filtrowania `typDokumentu` (zweryfikowane: suma
  per-typ zgadza się z sumą całkowitą co do grosza).
- `GET /api/hotel/sales-trend`, `/sales-breakdown`. Nowa zakładka „Hotel":
  trend + wykres/tabela TOP pozycji (89% to „Usługa zakwaterowania", reszta:
  parking, śniadania, rowery, zadatki).
- Znalezione przy okazji, NIE zbudowane (poza zakresem tej rundy — użytkownik
  wybrał start od `incomes`): `dailyhotelstats` (dzienna obsada/ADR/RevPAR,
  historia od **2015**) i `reservations` (13 467 rezerwacji, kanał sprzedaży,
  typ pokoju) — dobra baza pod przyszłe „plany sprzedażowe"/obłożenie.
  `hotellists` dodatkowo śledzi 13 konkurencyjnych hoteli w Trójmieście
  (rate shopping) — osobny temat, nie sprzedaż.

Wdrożone do Dockera. **Nie zcommitowane jeszcze.**

**Kategorie pozycji sprzedaży** (2026-08-26) — użytkownik chciał móc odfiltrować
np. wszystko związane z rowerem jedną etykietą zamiast pięciu osobnych pozycji.
`core/hotel_analytics._CATEGORY_RULES` — ręczna mapa znormalizowana nazwa →
kategoria (dziś tylko "Rowery": Rower 24"/20", Rower 28"/26", Rower z
fotelikiem, Wypożyczenie roweru, Kask — Płaszcz przeciwdeszczowy świadomie
WYŁĄCZONY, użytkownik zdecydował że nie należy do tej kategorii mimo że to też
akcesorium rowerowe), wszystko nieprzypisane ląduje w "Inne". Rozszerzanie:
dopisać kolejne wpisy do `_CATEGORY_RULES`, nic więcej nie trzeba zmieniać.
`get_sales_breakdown` zwraca teraz `kategoria` per pozycja + osobną listę
`categories` (suma/count/pct per kategoria). Frontend: nowa tabela "Sprzedaż
wg kategorii" nad breakdownem + dropdown "Kategoria" na zakładce Hotel, filtruje
wykres/tabelę pozycji po stronie klienta (bez dodatkowego zapytania — dane już
są w jednej odpowiedzi `/sales-breakdown`).

## Etap: dedup danych Mongo + Płatności/Rekordy + wydzielenie strony Hotel — 2026-09-18 ✅

**Problem:** wykres Hotel pokazywał sierpień 2026 na >1,06 mln zł zamiast
realnych ~552 tys. Przyczyna: system hotelowy synchronizuje `incomes`
okresowymi pełnymi eksportami, które nakładają się oknem czasowym (np. sync
25.08 objął 22.06-23.08, kolejny 01.09 cały sierpień od nowa) — te same
dokumenty trafiają do bazy drugi raz jako nowe wiersze (inny `_id`/`lp`).

- `utils/mongo_manager._dedupe_incomes` — klastruje `createdAt` w "przebiegi
  synchronizacji" (odstęp ≥1h = nowy przebieg; realne dane mają odstępy albo
  <15s w obrębie jednego przebiegu, albo >6 dni między przebiegami, więc
  próg jest bezpieczny). Klucz tożsamości: `nrParagonu`, a gdy brak — pole
  **`numerFaktury`** (osobne, prawdziwe pole w źródle — pierwsza wersja
  dopasowywała po treści, co przeoczało część duplikatów; poprawione po
  uwadze użytkownika). Oba pola mogą mieć kilka wierszy (wielopozycyjny
  paragon/faktura) — dla każdego klucza zatrzymujemy WSZYSTKIE wiersze z
  jego najnowszego przebiegu, nie tylko jeden, żeby nie ucinać legalnie
  powtórzonych tej samej pozycji w cenie.
- `get_incomes_trend`/`get_incomes_raw` liczą agregację w Pythonie (nie w
  pipeline Mongo) po deduplikacji.
- Zweryfikowane na żywych danych: różnica między naszą sumą a systemem
  źródłowym spadła z >500 tys. do ~45 tys. (dedup po `nrParagonu` samym), a
  po dodaniu `numerFaktury` doprecyzowanie nie zamknęło reszty luki —
  ostateczne domknięcie wymagało **pełnego reimportu danych od zera** przez
  program importujący użytkownika (nie tę aplikację — ta tylko czyta z
  Mongo). Po reimporcie: 0 duplikatów, suma styczeń-sierpień 3 272 304,35 zł
  vs system źródłowy 3 272 236,08 zł (różnica 68 zł, 0,002%).
- **Luka danych źródłowych, NIE naprawiona (poza zasięgiem tej aplikacji):**
  paragony `P 19/02/2026` i `P 339/02/2026` brakują w Mongo nawet po pełnym
  reimporcie — sąsiednie numery z tego samego dnia istnieją, zero śladu w
  całej bazie (też pod inną formą zapisu), i nie ma dla nich anulacji. Do
  sprawdzenia bezpośrednio w systemie hotelowym, jeśli ma to znaczenie.

**Nowe zakładki (na nowej podstronie, patrz niżej):**
- **Płatności** — rozbicie sprzedaży wg `formaPatnosci` (Gotówka/Przelew/
  Karta płatnicza + rzadkie płatności mieszane/puste) per miesiąc, wykres
  słupkowy skumulowany + tabele. `GET /api/hotel/payment-methods`.
- **Rekordy** — podgląd surowych wierszy z Mongo (bez deduplikacji), wiersze
  oznaczone `is_duplicate` wg tej samej reguły co wykres, przycisk usuwania
  pojedynczego rekordu z potwierdzeniem (nieodwracalne). `GET/DELETE
  /api/hotel/records[/{id}]`.

**Wydzielenie z Analityki na osobną podstronę `/hotel.html`** (na życzenie
użytkownika — dane Mongo to inny temat niż reszta Analityki, która jest
SQL-owa): `frontend/hotel.html` + `frontend/hotel.js` (self-contained, bez
buildu, ten sam wzorzec co `analityka.js`/`mailer.js` — duplikacja
helperów typu `fmtMoney`/`qs` celowa, zgodna z resztą projektu). Zakładki
Hotel/Płatności/Rekordy usunięte z `analityka.html`/`analityka.js`. Ikonka
🏨 w nagłówkach Faktur/Analityki/Mailera prowadzi do nowej strony.

## Dalszy plan działania

Zwięzłe podsumowanie tej listy jest też w `RAPORT_ANALITYKA.md` (sekcja 4) —
ten dokument tu zostaje źródłem prawdy, na bieżąco odznaczany/czyszczony.

- [ ] **Obsada/ADR/RevPAR z `dailyhotelstats`** — użytkownik świadomie
      zostawił to na później (start od `incomes`). Dane sięgają 2015, dobra
      podstawa pod plany sprzedażowe/obłożenie.
- [ ] **Kanały sprzedaży i typy pokoi z `reservations`** — jw., też
      świadomie odłożone.

- [x] ~~**CornerMarket** — jedyny z 6 głównych brandów bez śledzonego przychodu.~~
      Dodany 2026-08-24, uprawnienia SQL nadane i zweryfikowane — wszystkie 6
      brandów ma teraz przychód.
- [ ] **Alerty mailowe przy odchyleniu od prognozy** — apka ma już działający
      mailer; wymaga ustalenia progu (%), odbiorców i harmonogramu przed
      implementacją.
- [ ] **Pozostałe działy jako przychód** — jeśli któryś z „Pozostałych działów"
      (dziś: Kormoran, Konrad, Duba, Aurena, DRUK, „brak działu") jednak
      zacznie generować przychód, trzeba będzie dopisać go do
      `DOCHOD_NAMED_DZIALY` we `frontend/analityka.js`, żeby dostał własną
      kartę zamiast lądować w zbiorczej tabeli kosztowej.
- [ ] **Rozdzielenie prognozy cykliczne/jednorazowe** — baseline już wspiera
      filtr `cykliczna`, ale nie ma jeszcze osobnego, dedykowanego widoku
      "prognoza tylko dla kosztów cyklicznych" (stabilniejsze dane, tu
      faktyczny model ma najwięcej sensu). Do rozważenia jak segmentacja
      kontrahentów się ustabilizuje.
- [ ] **Backtest dla zakładki Trend kosztów** — `get_spend_forecast_backtest`
      już istnieje w backendzie (endpoint `/api/analytics/forecast-backtest`
      działa), ale nie ma jeszcze UI — dziś backtest jest widoczny tylko w
      „Trend wg działu” (przychód/dochód).
- [ ] **README** — krótki opis podstrony „Analityka" (wszystkie 7 zakładek,
      w tym Przegląd, prognoza, dochód, trend wg działu i backtest) wciąż
      nie dodany.
- [ ] **Przyczyna zrywania połączeń SQL** — nadal nieznana (prawdopodobnie
      limit bezczynności narzucony przez sieć/Docker NAT/SQL Server, poza
      zasięgiem tej aplikacji). Dziś w pełni wchłaniana przez heartbeat +
      retry, ale gdyby ktoś kiedyś miał dostęp do konfiguracji sieci między
      kontenerem a `192.168.30.14`, warto by to zdiagnozować u źródła.
- [ ] **Sprzątnięcie tego pliku planu** — do usunięcia po potwierdzeniu przez
      użytkownika, że całość (w tym wygląd, weryfikowany przez użytkownika w
      przeglądarce) działa zgodnie z oczekiwaniami.
