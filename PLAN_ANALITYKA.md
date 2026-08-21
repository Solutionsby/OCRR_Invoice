# Plan: Analityka (gałąź `analityka`)

Roboczy plik z etapami. Odznaczamy/usuwamy pozycje na bieżąco w miarę wdrażania i
weryfikowania. Zakres uzgodniony z użytkownikiem: trend kosztów w czasie, ranking
kontrahentów, struktura wg działu (historyczna), kategoria/podkategoria — na bazie
widoku `Faktury_Kosztowe_Zmapowane` (3609 wierszy, 2018-12–dziś, 706 kontrahentów,
12 zmapowanych działów, KATEGORIA wypełniona w 77%, PODKATEGORIA w 47%).
Wizualizacja: wykresy przez Chart.js (CDN). Domyślny zakres trendu: ostatnie 24
miesiące, z możliwością rozszerzenia w UI.

Poza zakresem tej rundy (świadomie pominięte): Kaucja (prawie nieużywana — 1
niezerowy wiersz na 3609), analityka opóźnień w płatnościach na
`FAKTURY_DO_ZAPLATY` (pole `CzyZaplacona` nigdy nie jest tam ustawiane na 1 —
dane niewiarygodne do tego celu, do wyjaśnienia osobno), anomalie/skoki, nowi vs.
stali kontrahenci.

## Etap 1 — Backend: agregacje SQL ✅
- [x] `utils/database_manager.py`: `get_spend_trend(year_from, month_from, year_to,
      month_to)` — GROUP BY rok/miesiąc na `Faktury_Kosztowe_Zmapowane`
- [x] `get_top_kontrahenci(year_from, month_from, year_to, month_to, limit)` — SUM
      brutto per kontrahent + osobna suma całkowita okresu (do liczenia %)
- [x] `get_dzial_trend(year_from, month_from, year_to, month_to)` — GROUP BY
      rok/miesiąc/dzial_docelowy
- [x] `get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial=None)`
      — GROUP BY KATEGORIA (COALESCE NULL/'' → "(brak kategorii)"), opcjonalny filtr
      działu
- [x] `get_podkategoria_breakdown(..., kategoria)` — jak wyżej, GROUP BY PODKATEGORIA
      w ramach wybranej kategorii
- [x] `core/analytics.py`: cienkie wrappery nad powyższym + liczenie % udziału
- [x] Weryfikacja: uruchomienie funkcji na żywej bazie (same SELECT-y). Znaleziony i
      naprawiony bug po drodze: `SUM(Kwota_Netto + Kwota_Vat)` w SQL gubił wiersze
      z NULL w jednej z kolumn (1 wiersz NULL netto, 2 NULL VAT w ostatnich 24
      mies. → różnica ~1318 zł); naprawione na
      `SUM(ISNULL(Kwota_Netto,0) + ISNULL(Kwota_Vat,0))` we wszystkich 4 funkcjach.
      Po poprawce: suma z `get_spend_trend` dla czerwca 2026 zgodna co do grosza z
      `get_kosztowe_by_month`, a totale wszystkich 4 funkcji dla ostatnich 24 mies.
      zgadzają się (6065329.09 zł, różnice tylko z zaokrągleń float).

## Etap 2 — API ✅
- [x] `api/schemas.py`: modele odpowiedzi (SpendTrendResponse, KontrahentRank...,
      DzialTrendResponse, KategoriaBreakdownResponse)
- [x] `api/routers/analytics.py`: `GET /api/analytics/trend`,
      `/kontrahenci`, `/dzialy-trend`, `/kategorie`, `/podkategorie`
- [x] `api/main.py`: podłączenie routera
- [x] Weryfikacja: `uvicorn` lokalnie (port 8010, poza kontenerem), wszystkie 4
      endpointy przetestowane curlem na żywych danych — odpowiedzi poprawne

## Etap 3 — Frontend ✅ (weryfikacja graficzna: użytkownik, w przeglądarce)
- [x] `frontend/analityka.html`: nowa podstrona, 4 zakładki (Trend, Kontrahenci,
      Działy, Kategorie), Chart.js z CDN, wzorowana na układzie `mailer.html`
- [x] `frontend/analityka.js`: fetch + wykresy (linia dla trendu, słupki dla
      rankingu kontrahentów, stacked bar dla działów, słupki z drill-down do
      podkategorii dla kategorii). Poprawka po pierwszym podglądzie: „(brak
      kategorii)” (29,6% wydatków) zostaje w tabeli, ale nie wchodzi na wykres —
      jako największa pozycja spłaszczał do zera słupki wszystkich realnych
      kategorii na wspólnej skali.
- [x] `frontend/styles.css`: `.an-chart-box`/`.an-chart-box-tall` (reszta reużyta:
      `mailer-page`, `mailer-tabs`, `dzial-breakdown-table`)
- [x] Link nawigacyjny (ikona 📊) w `index.html` i `mailer.html` (+ odwrotny link do
      mailera z analityki)
- [x] Weryfikacja funkcjonalna (moja): lokalny headless test — 4 zakładki, filtr
      działu, drill-down kategoria→podkategoria, zero błędów w konsoli JS.
      **Weryfikacja graficzna (wygląd/UX) — robi użytkownik sam w przeglądarce**,
      zgodnie z ustaleniem w tej rozmowie.
- [x] Wdrożone do Dockera: `docker compose up --build -d`, kontener
      `ocrr_invoice-api-1` przebudowany i działa na http://localhost:8000 —
      `/analityka.html` i `/api/analytics/*` odpowiadają poprawnie.

## Etap 3b — poprawki po pierwszym przeglądzie użytkownika ✅
- [x] Kategoria/Podkategoria: 155 surowych wartości KATEGORIA scalone do 143 —
      warianty różniące się tylko brakiem polskich znaków (np. „Częsci"/„Cześci"/
      „Czesci"/„Części") łączone przez `core/analytics._merge_variants` +
      `_normalize_label`. Drill-down do podkategorii poprawiony, żeby dociągał
      WSZYSTKIE warianty scalonej kategorii (`db.get_podkategoria_breakdown`
      przyjmuje teraz listę wariantów, nie jeden string).
- [x] Kontrahenci: filtr „Dział" (dropdown, reużywa `/api/mailer/monthly/dzialy`)
      — `db.get_top_kontrahenci`/`core.analytics.get_top_kontrahenci`/router
      przyjmują opcjonalny `dzial`.
- [x] Wdrożone do Dockera po każdej poprawce.

## Etap 3c — prosty baseline prognozy kosztów ✅
Kontekst: użytkownik równolegle segmentuje bazę na koszty cykliczne/jednorazowe;
to na razie NIE jest tego wykorzystuje — prosty statystyczny baseline na
istniejącym `get_spend_trend`, jawnie NIE model ML (uzgodnione w rozmowie: dane
są zbyt nierówne — pojedyncze duże faktury dominują miesiące — żeby ufać
czarnej skrzynce).
- [x] `core/analytics.py`: `_contiguous_history()` (najdłuższy ciągły ogon
      historii miesiąc-do-miesiąca, żeby odległe pojedyncze wpisy z 2018/2023
      nie zniekształcały sezonowości) + `get_spend_forecast(months_ahead=3)`:
      wskaźnik sezonowości = mediana brutto danego miesiąca kalendarzowego /
      mediana całej historii; poziom = mediana z ostatnich (do 12) miesięcy PO
      odsezonowaniu; prognoza = poziom × wskaźnik. Mediana wszędzie (nie
      średnia) — odporność na skoki.
      Poprawka po pierwszym uruchomieniu: bieżący (niedokończony) miesiąc
      wykryty i wykluczony ze statystyk (zostaje widoczny w historii, ale nie
      zaniża poziomu/sezonowości) — inaczej sierpień 2026 (1 faktura, dane
      częściowe) fałszywie wyglądał jak słaby miesiąc.
- [x] `api/schemas.py` + `api/routers/analytics.py`: `GET /api/analytics/forecast?months_ahead=N`
- [x] `frontend`: zakładka Trend — checkbox „Pokaż prognozę" + liczba miesięcy
      naprzód, kropkowana linia doklejona do wykresu rzeczywistych kosztów,
      status z liczbą miesięcy historii użytych do baseline'u
- [x] Weryfikacja na żywych danych: 32 ciągłe miesiące historii (2024-01–2026-08;
      pojedyncze wpisy z 2018-12 i 2023 poprawnie odcięte przez
      `_contiguous_history`), sezonowość sensowna dla biznesu hotelarskiego
      (szczyt czerwiec ×2.4, dołek luty ×0.58). Wdrożone do Dockera.
- [x] Segmentacja po stronie użytkownika gotowa: tabela `dbo.KONTRAHENCI_CYKLICZNI`
      (Nazwa_Kontrahenta PK, CzyCykliczna BIT, Uwagi, DataOznaczenia) +
      `ALTER VIEW Faktury_Kosztowe_Zmapowane` z `LEFT JOIN` i
      `COALESCE(kc.CzyCykliczna, 0) AS CzyCykliczna` — 55 kontrahentów
      oznaczonych, 2041 faktur cyklicznych / 1565 jednorazowych na żywo.
- [x] Dociągnięcie do backendu: `db.get_spend_trend(..., cykliczna=None|True|False)`
      (filtr `AND CzyCykliczna = ?`), `core.analytics.get_spend_trend`/
      `get_spend_forecast` przyjmują ten sam parametr, `GET /api/analytics/trend`
      i `/forecast` mają query param `cykliczna`. Zweryfikowane na żywych
      danych: cykliczne + jednorazowe = wszystkie, co do grosza
      (4271606.93 + 3845441.89 = 8117048.82).
- [x] Frontend: zakładka Trend — dropdown „Rodzaj kosztów" (wszystkie/cykliczne/
      jednorazowe), filtruje jednocześnie wykres rzeczywistych kosztów i
      prognozę. Cykliczne mają pełne 32 mies. ciągłej historii (z definicji —
      to one były kryterium doboru), jednorazowe z natury bardziej nieregularne.
- [x] Wdrożone do Dockera. **Nie zcommitowane jeszcze** — czeka na sygnał do
      commitu/merge (jak poprzednio).
- [x] Bug znaleziony przy pytaniu użytkownika „czemu styczeń 2026 > styczeń
      2027 w prognozie": to NIE był błąd modelu (matematycznie prognoza
      styczeń 2027 wychodzi WYŻEJ niż realny styczeń 2026 — sprawdzone
      liczbowo), tylko błąd rysowania wykresu we `frontend/analityka.js`.
      Backend prognozuje na nowo bieżący niedokończony miesiąc jako pierwszy
      punkt prognozy (ta sama etykieta co ostatni realny punkt), a front tego
      nie rozpoznawał — doklejał go jako DODATKOWĄ, zduplikowaną etykietę
      miesiąca, przesuwając całą resztę prognozy (w tym styczeń) o jedną
      pozycję na osi X. Naprawione: front wykrywa nakładający się miesiąc i
      nie duplikuje etykiety. Wdrożone do Dockera.

## Etap 3d — Dochód (przychód − koszt) wg działu ✅
Użytkownik zbudował osobną bazę `Przychody` (tabela `Przychody.dbo.Przychod_Netto`:
Dzial, Rok, Miesiac, KwotaNetto), agregującą przychody z tabel działowych.
Na razie 2 działy (Hotel, Automaty), reszta dochodzi sukcesywnie.
- [x] Uprawnienia: login `PYTHON` (`.env`/`DB_USER`) dostał `SELECT` na bazie
      `Przychody` ORAZ na bazach źródłowych, z których korzysta widok
      `Przychod_Netto` (np. „Sopocki Zdroj” — cross-database query rzuciła
      błędem permission denied, dopóki nie nadano dostępu też tam).
- [x] `utils/database_manager.get_dochod()`: JEDNO zapytanie, `FULL OUTER JOIN`
      między `Faktury_Kosztowe_Zmapowane` (koszt netto per dział/miesiąc) a
      `Przychody.dbo.Przychod_Netto` (cross-database, ten sam serwer SQL) —
      brakująca strona wraca jako `None`, nie 0 (nie sugerować fałszywego
      dochodu/straty dla działów bez śledzonego przychodu).
- [x] `core/analytics.get_dochod()`: agreguje per dział za cały wybrany okres
      + `total_*` liczone TYLKO z działów, które mają przychód (inaczej suma
      kosztów 10 działów minus przychód 2 dałaby fałszywie ogromną „stratę”)
      + `dzialy_bez_przychodu` jawnie wylistowane.
- [x] `api/schemas.py` + `api/routers/analytics.py`: `GET /api/analytics/dochod`
- [x] Frontend: nowa zakładka „Dochód” — tabela dział/koszt/przychód/dochód,
      domyślny zakres Od=2024-01 (nie „ostatnie 24 mies.” jak gdzie indziej —
      to próg, od którego historia kosztów jest ciągła), ostrzeżenie w UI gdy
      zakres cofnięty przed 2024-01 (koszt niekompletny → dochód zawyżony).
- [x] Weryfikacja na żywych danych (2024-01–2026-08): Hotel koszt 1 041 235,32 /
      przychód 9 969 082,31 / dochód 8 927 846,99; Automaty koszt 887 594,63 /
      przychód 926 519,04 / dochód 38 924,41. Zweryfikowana też pułapka: pełny
      zakres od 2019 dawał total_dochod=18,58M (zawyżone, bo Hotel ma przychód
      od 2019 ale koszt w bazie realnie dopiero od 2024) — stąd domyślny
      zakres i ostrzeżenie w UI. Działa też cross-database z wnętrza
      kontenera Docker (te same poświadczenia SQL).
- [x] Rozbicie widoku (czysto front-end, `GET /api/analytics/dochod` bez zmian):
      6 wymienionych działów (CornerMarket, Hotel, RDS, Gastronomia, Automaty,
      Wspólne) dostaje własną kartę bilansu (`.an-dochod-card`, kolor
      zielony/czerwony wg znaku dochodu), reszta działów zbiorczo w tabeli
      „Pozostałe działy” poniżej (ta sama co dotąd, tylko odfiltrowana o tych
      6). Zweryfikowane na żywych danych: wszystkie 6 nazwanych obecne w
      wyniku, reszta (Kormoran, Konrad, Duba, „(brak działu)”, Aurena, DRUK)
      poprawnie trafia do tabeli zbiorczej. Wdrożone do Dockera.
- [x] Karta „Brandy łącznie” — suma koszt/przychód/dochód TYLKO z tych spośród
      6 nazwanych brandów, które mają śledzony przychód (dziś: Hotel, RDS,
      Automaty, Gastronomia, Wspólne — 5/6, brakuje CornerMarket), etykieta
      pokazuje ile z 6 wchodzi w sumę. Tabela „Pozostałe działy” dostała
      wiersz sumy (Koszt zawsze, Przychód/Dochód tylko jeśli któryś z reszty
      ma dane) i sortowanie malejąco po koszcie (nie po dochodzie — większość
      tych działów nie ma jeszcze przychodu). Wdrożone do Dockera.
- [x] Zmiana semantyki na życzenie użytkownika: brak śledzonego przychodu = 0 zł
      przychodu (nie "brak danych"), więc `dochod` jest ZAWSZE liczbą (ujemną,
      gdy przychód nieznany — dochod = −koszt) i WSZYSTKIE działy wchodzą do
      sum/kart (`core/analytics.get_dochod`, `api/schemas.DochodItem.dochod:
      float`, nie `float | None`). `przychod_netto` samo w sobie zostaje
      `None` gdy nietrackowane — dalej odróżnia "wiemy że 0" od "jeszcze nie
      wiemy". Karta „Brandy łącznie” i wiersz sumy „Pozostałe działy” sumują
      teraz wszystkich, kolor czerwony/zielony w każdym wierszu. Zweryfikowane
      na żywych danych (2024-01–2026-08): suma `dochod` per dział = total_dochod
      co do grosza (6 981 624,57 zł); przykład ujemnego: Wspólne
      koszt 1 530 874,83 / przychód 237 422,34 / dochód **−1 293 452,49**.
      Wdrożone do Dockera.
- [x] Doprecyzowanie na życzenie użytkownika: „Pozostałe działy” (poza 6
      głównymi brandami) nigdy nie będą generować przychodu (koszty
      wsparcia/ogólne) — tabela zredukowana do Dział/Koszt (bez
      Przychód/Dochód, które tam były bez sensu). „Łącznie” na górze strony
      zmienione tak, żeby liczyć TYLKO 6 brandów (spójnie z kartą „Brandy
      łącznie” — usunięty zdublowany tekst statusu, karta jest teraz jedynym
      źródłem tej liczby). Wdrożone do Dockera.

## Etap 4 — domknięcie
- [ ] README: krótki opis nowej podstrony „Analityka" (w tym prognoza)
- [ ] Usunięcie tego pliku planu po potwierdzeniu przez użytkownika, że wszystko
      działa zgodnie z oczekiwaniami (w tym wygląd — do potwierdzenia przez
      użytkownika)
