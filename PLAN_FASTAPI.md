# Plan: CLI → FastAPI + JS frontend (Docker)

Roboczy plik z etapami. Odznaczamy/usuwamy pozycje na bieżąco w miarę wdrażania i
weryfikowania. Pełne uzasadnienie architektury: patrz commit wiadomość / historia
konwersacji przy pierwszym wdrożeniu tego pliku.

## Etap 0 — fundament pod Dockera i wspólny kod
- [x] `core/paths.py`: `BASE_PATH` z env var `INVOICES_BASE_PATH` (pierwszeństwo, do
      Dockera), fallback na dzisiejszą logikę `platform.system()` dla CLI bez kontenera
- [x] `requirements.txt`: dopisać brakujący `python-dotenv` + `fastapi`,
      `uvicorn[standard]`, `python-multipart`
- [x] `Dockerfile`: `python:3.11-slim`, `tesseract-ocr`+`tesseract-ocr-pol`,
      `poppler-utils`, ODBC Driver 17 for SQL Server (repo Microsoftu), pip install
      (+ placeholder `api/main.py` z `/health`, tylko żeby zweryfikować że kontener
      wstaje — pełne routery dochodzą w Etapie 2)
- [x] `docker-compose.yml`: serwis `api`, `env_file: .env`, bind mounty
      `faktury_surowe/`, `faktury_przetworzone/` → `/data/...` (zgodnie z
      `INVOICES_BASE_PATH`), `json/`, `patterns.json`, `settings.json` → `/app/...`
      (te są czytane ścieżkami względnymi wobec CWD w istniejącym kodzie), port
      `8000:8000`
- [x] Weryfikacja: `docker compose up --build` wstaje, `docker compose exec api ls
      /data/faktury_surowe` widzi pliki z hosta (potwierdzone: `.DS_Store`, `euro/`,
      `inne/` widoczne w kontenerze; `/app/json`, `/app/patterns.json`,
      `/app/settings.json` też poprawnie zamontowane)
- [x] Sprawdzić czy `.env` (`DB_SERVER`/`SMTP_SERVER`) wymaga zmiany na
      `host.docker.internal` — **nie wymaga**: `DB_SERVER=192.168.30.14\SQLEXPRESS`
      i `SMTP_SERVER=wn08.webd.pl` to realne adresy w sieci, nie `localhost`, więc
      domyślny bridge network Dockera wystarcza. Potwierdzone żywym połączeniem z
      wnętrza kontenera (`SELECT 1`, tylko odczyt) — zadziałało od razu.
      Po drodze wyszedł prawdziwy problem z montowaniem/budową: `msodbcsql17` nie
      ma kompletnych paczek arm64 na Debianie 12 (Apple Silicon) i apt się wykładał.
      Przełączono na `msodbcsql18` + odkryto i podłączono nieużywaną dotąd zmienną
      `DB_DRIVER` z `.env` w `utils/database_manager.py` (host/CLI zostaje przy
      Driver 17, kontener dostaje Driver 18 przez override w docker-compose.yml) —
      to prawdopodobnie było źródło wcześniejszego blokera z montowaniem.

## Etap 1 — KSeF: `core/ksef.py` + CLI wrapper
- [x] Wydzielić `analyze_ksef(pdf_path)` z `main.py` (heurystyka statusu płatności
      jako flaga `payment_status_ambiguous`, nie prompt)
- [x] Wydzielić `finalize_ksef(pdf_path, data, action)` (rename/route/move/DB/knowledge)
- [x] Przepisać `main.py` na wrapper: `analyze_ksef` → `utils/ui_handler` (UX terminala
      bez zmian) → `finalize_ksef`. Import-check przeszedł (`import main`,
      `import core.ksef` bez błędów).
- [x] Weryfikacja `analyze_ksef` (czysta ekstrakcja, bez ruszania plików/DB): 15/15 z
      próbki co 10. pliku z 142 realnych faktur wrzuconych do `faktury_surowe/`
      przeszło bez błędu, dane sensowne (firma/numer/data/termin/status/brutto)
- [x] Weryfikacja pełnego `finalize_ksef` (rename+move+SQL write) — użytkownik
      przepuścił realne faktury przez `python run.py`: działa identycznie jak
      przed refaktorem. Etap 1 zamknięty.

## Etap 2 — API + frontend dla KSeF
- [x] `api/schemas.py`, `api/routers/ksef.py`: `GET /api/ksef/invoices`,
      `GET /api/ksef/invoices/{id}`, `GET /api/ksef/invoices/{id}/file`,
      `POST /api/ksef/invoices/{id}/finalize`
- [x] `api/main.py`: FastAPI app, mount routera, serwowanie `frontend/` jako static
- [x] `frontend/`: lista faktur, `<iframe>` z podglądem PDF, formularz korekty,
      przyciski Tak/Nie-korekta/Kolejkuj/Pomiń, finalize, toast z wynikiem zapisu
- [x] Weryfikacja end-to-end lokalnie i w kontenerze na realnych fakturach KSeF
      (plik na dysku hosta w poprawnym folderze + wpis w SQL potwierdzony odczytem)
      i ręcznie w przeglądarce przez użytkownika. Etap 2 zamknięty.

  Po drodze naprawione 3 błędy złapane w przeglądarce (nie wychwycone przez testy
  API, bo dotyczyły zachowania przeglądarki/JS):
  1. `FileResponse` domyślnie wysyłał `Content-Disposition: attachment` — PDF
     próbował się pobierać zamiast wyświetlić w `<iframe>`. Fix:
     `content_disposition_type="inline"`.
  2. Wyścig asynchroniczny w `app.js`: OCR trwa różnie długo dla różnych faktur,
     więc odpowiedzi `GET /invoices/{id}` mogły wrócić w innej kolejności niż
     kliknięcia — formularz zostawał nadpisany danymi starszego kliknięcia. Fix:
     odrzucanie odpowiedzi, jeśli `currentId` zmienił się w międzyczasie.
  3. Pole „Kontrahent" nie aktualizowało się mimo poprawki #2 (prawdopodobnie
     interferencja autouzupełniania przeglądarki dla pola nazwanego jak dane
     firmy). Fix: jawny dostęp przez `form.elements.namedItem(...)` zamiast
     `form.<name>`, plus `autocomplete="off"` na formularzu.

## Etap 3 — „inne" (spoza KSeF)
- [x] `core/inne.py`: `analyze_inne`/`finalize_inne` (dział/kategoria i opłacona jako
      pola formularza, nie blokujące prompty; brutto zawsze przeliczane server-side
      jako netto+vat, nigdy przyjmowane wprost)
- [x] Przepisać `main_inne.py` na wrapper nad `core/inne.py`
- [x] `api/routers/inne.py` (+ wydzielony `api/routers/common.py: resolve_pdf`,
      reużyty też w `ksef.py`) + zakładki KSeF/Spoza KSeF w `frontend/`
      (pola dział/kategoria/opłacona/netto/VAT dla "inne", status/forma/brutto
      dla KSeF — przełączane przez `[data-flow]` w HTML)
- [ ] Weryfikacja jak w Etapie 2, na próbce faktur spoza KSeF — **czeka na
      przykładowe pliki w `faktury_surowe/inne/`**, API/import-checki przeszły

## Etap 4 — EURO
- [x] `core/euro.py`: `analyze_euro`/`finalize_euro` (kurs NBP jako sugestia edytowalna,
      `None` gdy NBP nie odpowie — wtedy pole wymagane ręcznie; opis z ekwiwalentem
      EUR+kursem trafia do `FAKTURY_KOSZTOWE.Opis` jak w dawnym main_euro.py)
- [x] Przepisać `main_euro.py` na wrapper nad `core/euro.py`
- [x] `api/routers/euro.py` + trzecia zakładka EURO we frontendzie (dział/kategoria/
      opłacona/netto/VAT współdzielone z "inne" przez `data-flow="inne euro"`, plus
      kurs EUR/PLN i podgląd kwot źródłowych EUR, z przeliczeniem na żywo)
- [x] Weryfikacja backendu: **żywy test end-to-end** na realnej fakturze EUR
      (Aurena GmbH, 237,90 EUR → kurs NBP 4,2768 → 1017,45 PLN) — plik trafił na
      dysk hosta do `do_zaplaty/`, wpis potwierdzony w obu tabelach: `FAKTURY_KOSZTOWE`
      (netto/vat/dzial/kategoria/opis ze śladem przeliczenia) i `FAKTURY_DO_ZAPLATY`.
      Backend + API w pełni zweryfikowane. **UI w przeglądarce czeka na ręczne
      sprawdzenie przez użytkownika** (nie mam w tej sesji dostępu do przeglądarki).

## Etap 5 — domknięcie
- [ ] Pełny regres CLI (`python run.py`, wszystkie 3 opcje) po wszystkich refaktorach
- [ ] README: opis uruchomienia przez `docker compose up` obok opisu CLI

## Etap 6 — sprawdzanie duplikatów i wyszukiwarka (dodane na życzenie 2026-08-14)
- [x] `utils/database_manager.py: find_duplicates(numer)` — szuka numeru faktury w
      obu tabelach (FAKTURY_DO_ZAPLATY, FAKTURY_KOSZTOWE), tylko odczyt
- [x] Podpięte we wszystkich trzech `analyze_*` (`core/ksef.py`, `core/inne.py`,
      `core/euro.py`) — działa automatycznie w CLI i w API, nie tylko w przeglądarce
- [x] `duplicate_matches` w schematach `InvoiceProposal*`, baner ostrzegawczy w
      formularzu (frontend) gdy numer już jest w bazie
- [x] `utils/database_manager.py: search_invoices(numer, kontrahent)` — częściowe
      dopasowanie (LIKE) w obu tabelach, wymaga min. jednego kryterium
- [x] `api/routers/search.py: GET /api/search` + przycisk 🔍 w sidebarze otwierający
      modal z wynikami (niezależny od aktualnie przeglądanej zakładki/faktury)
- [x] Zweryfikowane na żywo w kontenerze przeciw produkcyjnej bazie: `find_duplicates`
      poprawnie znajduje wcześniej zapisaną fakturę AKA Sp. z o.o., `search_invoices`
      zwraca trafne wyniki po numerze i po kontrahencie (21 dopasowań dla "Aurena")

---
**Poza zakresem:** `mail_sender.py`, `payment_manager.py` zostają jako osobne
skrypty CLI/cron — bez UI w przeglądarce w tej rundzie.
