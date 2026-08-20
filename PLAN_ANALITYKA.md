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
- [ ] **Do zrobienia po stronie użytkownika**: segmentacja bazy na koszty
      cykliczne/jednorazowe — gdy gotowe, warto rozbudować baseline (osobna
      prognoza dla kosztów cyklicznych, inaczej dla jednorazowych) albo dodać
      prawdziwy model tylko dla cyklicznych (stabilniejsze dane).

## Etap 4 — domknięcie
- [ ] README: krótki opis nowej podstrony „Analityka" (w tym prognoza)
- [ ] Usunięcie tego pliku planu po potwierdzeniu przez użytkownika, że wszystko
      działa zgodnie z oczekiwaniami (w tym wygląd — do potwierdzenia przez
      użytkownika)
