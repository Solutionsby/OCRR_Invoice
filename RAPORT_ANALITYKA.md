# Raport: Analityka — co powstało (2026-08-20 – 2026-08-24)

Podsumowanie prac nad podstroną `/analityka.html`. Szczegółowy, chronologiczny
zapis (z uzasadnieniami, pomiarami, historią debugowania) jest w
`PLAN_ANALITYKA.md` — ten dokument to czytelne podsumowanie „co jest gotowe
i po co”, nie dziennik prac.

Stan: zmergowane do `main`, wdrożone na `http://localhost:8000`.

## 1. Dashboard — 7 zakładek

Wszystkie na widoku `Faktury_Kosztowe_Zmapowane` (koszty) połączonym z
`Przychody.dbo.Przychod_Netto` (przychody, cross-database).

1. **Przegląd** — pierwsza strona, 6 kart: ten miesiąc (cała firma), prognoza
   na przyszły miesiąc, zmiana kosztów m/m, cykliczne vs jednorazowe (rok
   bieżący), ranking brandów wg dochodu, uwagi (np. brakujący przychód).
2. **Trend kosztów** — miesięczny trend, filtr wszystkie/cykliczne/
   jednorazowe, prosty baseline prognozy (mediana + sezonowość).
3. **Kontrahenci** — ranking TOP N wg wydatków, filtr działu.
4. **Działy** — struktura kosztów wg działu w czasie.
5. **Kategorie** — 155 surowych wartości KATEGORIA scalone do 143 (literówki/
   brak polskich znaków), drill-down do podkategorii, filtr działu i
   cykliczne/jednorazowe.
6. **Dochód** — koszt vs przychód netto per dział za wybrany okres. Karta
   „Brandy łącznie” (6 głównych: CornerMarket, Hotel, RDS, Gastronomia,
   Automaty, Wspólne) + marża %, karty per brand posortowane od najlepszego
   do najgorszego wyniku, tabela pozostałych działów (same koszty — te nigdy
   nie będą miały przychodu).
7. **Trend wg działu** — jeden dział (albo suma wszystkich 6) na raz,
   porównanie miesiąc-do-miesiąca między latami (słupki dla lat przeszłych,
   linia dla bieżącego roku), własna prognoza przychodu i dochodu, oraz
   **tabela trafności prognozy** — dla ostatnich N miesięcy pokazuje, co
   model przewidziałby używając tylko danych sprzed tego miesiąca, zestawione
   z rzeczywistym wynikiem.

## 2. Co warto wiedzieć o danych (odkryte po drodze)

- **Rzetelna, ciągła historia kosztów zaczyna się dopiero 2024-01** —
  wcześniejsze wpisy (2018, 2023) to pojedyncze, odosobnione rekordy.
  Wszystkie domyślne zakresy i ostrzeżenia w UI są dobrane pod ten próg.
- **Przychód nie ma tego ograniczenia** — Hotel ma sensowną historię
  przychodu od 2018/2019, więc porównania lat na „Trend wg działu” mają sens
  dużo głębiej wstecz niż strona kosztowa.
- **Marża bardzo różni się między brandami**: Hotel ~90%, RDS ~44%,
  Automaty ledwie na plusie (~4%) — w złotówkach nieporównywalne ze względu
  na skalę, w % widać wyraźnie, kto jest efektywny.
- **Segmentacja cykliczne/jednorazowe** — 55 kontrahentów oznaczonych jako
  cykliczni w `KONTRAHENCI_CYKLICZNI` (flaga per kontrahent, nie per
  faktura), pozwala rozdzielić trend/prognozę/kategorie na koszty stałe vs
  jednorazowe zakupy.
- **Sezonowość biznesu hotelarskiego jest wyraźna** — szczyt czerwiec-lipiec
  (wskaźnik nawet ×2,7 średniej), dołek styczeń-luty (×0,5-0,6).
- Prognoza to celowo **prosty baseline (mediana + wskaźnik sezonowości), NIE
  model ML** — dane są zbyt nierówne (pojedyncze duże faktury/transakcje
  potrafią zdominować miesiąc), żeby ufać czarnej skrzynce. Backtest pokazuje
  wprost, jak dobry/zły jest ten baseline dla konkretnego działu.

## 3. Stabilizacja infrastruktury (warstwa SQL)

Osobny, ważny wątek tej rundy — dashboard uruchomił dużo więcej ruchu do
bazy niż wcześniej, co ujawniło realne problemy z warstwą połączeń
(`utils/database_manager.py`), naprawiane kolejno w miarę jak się
ujawniały:

1. **Jedno trwałe połączenie SQL** zamiast otwierania nowego przy każdym z
   ~14 zapytań — nawiązanie połączenia z tym serwerem jest bardzo drogie
   (zmierzone: >100s), a dawny wzorzec płacił ten koszt praktycznie za
   każdym razem.
2. **Lock serializujący dostęp** — naprawił żywy crash: dwa jednoczesne
   zapytania cross-database dawały connection reset (10054) z serwera.
3. **Retry na poziomie zapytania** (nie osobnym prefetch-checkiem) — łapie
   zerwane połączenie dokładnie tam, gdzie występuje, i naprawia się
   przezroczyście.
4. **Wyłączona pula połączeń sterownika ODBC** — oddawała martwe połączenia
   z własnej puli, co powodowało kaskady kilkudziesięciu błędów pod rząd.
5. **Jawne limity czasu** (connect/query) — bez nich zawieszona sieć
   potrafiła zablokować CAŁĄ aplikację na >12 minut bez żadnego logu błędu,
   wymagając ręcznego restartu. Teraz każde zawieszenie zamienia się w
   rzucony wyjątek, który system już umie złapać i naprawić.
6. **Rozgrzewanie + heartbeat przy starcie kontenera** — pierwszy prawdziwy
   użytkownik po restarcie nie płaci już kosztu nawiązania połączenia;
   heartbeat co 30s nie dopuszcza do bezczynności wystarczająco długiej, by
   coś po drodze (Docker NAT / firewall / sam SQL Server) zabiło sesję.
7. **Leniwe ładowanie zakładek** we frontendzie — strona nie odpytuje już
   wszystkich 7 zakładek naraz przy otwarciu, tylko dociąga dane przy
   pierwszym kliknięciu w daną zakładkę.

Efekt: typowe zapytanie spadło z dziesiątek/setek sekund do 1-5s.

**Uczciwa uwaga:** źródłowa przyczyna zrywania połączeń (prawdopodobnie
limit bezczynności narzucony przez sieć albo sam SQL Server) nie została
wyeliminowana — jest wchłaniana w tle przez heartbeat i retry, więc
użytkownik jej nie widzi, ale nie da się jej naprawić z poziomu kodu tej
aplikacji.

## 4. Dalsze prace

Aktualna, prowadzona na bieżąco lista w `PLAN_ANALITYKA.md`, sekcja
„Dalszy plan działania”.
