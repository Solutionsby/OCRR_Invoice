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
- [ ] Wydzielić `analyze_ksef(pdf_path)` z `main.py` (heurystyka statusu płatności
      jako flaga `payment_status_ambiguous`, nie prompt)
- [ ] Wydzielić `finalize_ksef(pdf_path, data, action)` (rename/route/move/DB/knowledge)
- [ ] Przepisać `main.py` na wrapper: `analyze_ksef` → `utils/ui_handler` (UX terminala
      bez zmian) → `finalize_ksef`
- [ ] Weryfikacja: `python run.py` opcja `[1]` działa jak przed refaktorem na próbce
      realnych faktur KSeF

## Etap 2 — API + frontend dla KSeF
- [ ] `api/schemas.py`, `api/routers/ksef.py`: `GET /api/ksef/invoices`,
      `GET /api/ksef/invoices/{id}`, `GET /api/ksef/invoices/{id}/file`,
      `POST /api/ksef/invoices/{id}/finalize`
- [ ] `api/main.py`: FastAPI app, mount routera, serwowanie `frontend/` jako static
- [ ] `frontend/`: lista faktur, `<iframe>` z podglądem PDF, formularz korekty,
      przyciski Tak/Nie-korekta/Kolejkuj/Pomiń, finalize
- [ ] Weryfikacja end-to-end w kontenerze na 1 realnej fakturze KSeF (plik na dysku
      hosta w poprawnym folderze + wpis w SQL, zapytanie pokazane przed uruchomieniem)

## Etap 3 — „inne" (spoza KSeF)
- [ ] `core/inne.py`: `analyze_inne`/`finalize_inne` (dział/kategoria i opłacona jako
      pola formularza, nie blokujące prompty)
- [ ] Przepisać `main_inne.py` na wrapper nad `core/inne.py`
- [ ] `api/routers/inne.py` + rozszerzenie frontendu
- [ ] Weryfikacja jak w Etapie 2, na próbce faktur spoza KSeF

## Etap 4 — EURO
- [ ] `core/euro.py`: `analyze_euro`/`finalize_euro` (kurs NBP jako pole edytowalne)
- [ ] Przepisać `main_euro.py` na wrapper nad `core/euro.py`
- [ ] `api/routers/euro.py` + pole kursu EUR/PLN we frontendzie
- [ ] Weryfikacja jak w Etapie 2, na próbce faktur EUR

## Etap 5 — domknięcie
- [ ] Pełny regres CLI (`python run.py`, wszystkie 3 opcje) po wszystkich refaktorach
- [ ] README: opis uruchomienia przez `docker compose up` obok opisu CLI

---
**Poza zakresem:** `mail_sender.py`, `payment_manager.py` zostają jako osobne
skrypty CLI/cron — bez UI w przeglądarce w tej rundzie.
