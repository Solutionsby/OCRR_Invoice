import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.paths import BASE_PATH, source_dir_ksef, source_dir_inne, source_dir_euro, dest_dir, ensure_dirs
from utils import database_manager as db
from api.routers import ksef as ksef_router
from api.routers import inne as inne_router
from api.routers import euro as euro_router
from api.routers import search as search_router
from api.routers import mailer as mailer_router
from api.routers import folders as folders_router
from api.routers import analytics as analytics_router

ensure_dirs()

app = FastAPI(title="OCRR Invoice API")


def _warmup_db():
    """
    Nawiązanie połączenia SQL i pierwszy dostęp cross-database do bazy
    Przychody są bardzo drogie (zmierzone na żywo: pyodbc.connect() >100s,
    pierwsze zapytanie cross-database kolejne >30s — patrz
    utils/database_manager.py i PLAN_ANALITYKA.md). Bez tego pierwszy
    prawdziwy użytkownik po (re)starcie kontenera płaciłby ten koszt sam,
    czekając ~2 minuty na zakładkę Dochód. Odpalane w tle wątkiem-daemonem,
    żeby NIE blokować startu serwera (health check ma odpowiadać od razu).
    Zakres dat dobrany tak, żeby zapytanie dotknęło Przychody, ale nie
    zwracało realnych wierszy do przetworzenia.
    """
    try:
        db.get_dochod(2000, 1, 2000, 1)
    except Exception:
        pass  # samo "rozgrzanie" połączenia — realny błąd i tak złapie się przy pierwszym prawdziwym użyciu


@app.on_event("startup")
def _on_startup():
    threading.Thread(target=_warmup_db, daemon=True).start()
    # Bez tego dłuższa przerwa w ruchu = połączenie stoi bezczynnie i coś po
    # drodze (Docker NAT / firewall / sam SQL Server) je ubija — zaobserwowane
    # na żywo nawet na zwykłych, niedotykających Przychody zapytaniach (patrz
    # utils/database_manager._keepalive_loop).
    db.start_keepalive()


@app.middleware("http")
async def no_cache_static(request, call_next):
    """
    Frontend (index.html/app.js/styles.css) jest bez builda i zmienia się
    często w trakcie rozwoju — bez tego przeglądarka potrafi trzymać starą
    wersję app.js z heurystycznego cache'u (brak Cache-Control ze
    StaticFiles), przez co świeżo wgrane zmiany "nie działają" mimo
    poprawnego kodu na serwerze, dopóki ktoś nie zrobi twardego odświeżenia.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(ksef_router.router)
app.include_router(inne_router.router)
app.include_router(euro_router.router)
app.include_router(search_router.router)
app.include_router(mailer_router.router)
app.include_router(folders_router.router)
app.include_router(analytics_router.router)


@app.get("/health")
def health():
    dirs = {
        "base_path": BASE_PATH,
        "ksef_source": source_dir_ksef(),
        "inne_source": source_dir_inne(),
        "euro_source": source_dir_euro(),
        "dest": dest_dir(),
    }
    return {
        "status": "ok",
        **{name: str(path) for name, path in dirs.items()},
        **{f"{name}_exists": path.exists() for name, path in dirs.items()},
    }


# Statyczny frontend (bez builda) — musi być zamontowany na końcu, żeby nie
# przechwycił ścieżek /api/* i /health zadeklarowanych wyżej.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
