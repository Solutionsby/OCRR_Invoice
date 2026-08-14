from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.paths import SOURCE_DIR, ensure_dirs
from api.routers import ksef as ksef_router
from api.routers import inne as inne_router
from api.routers import euro as euro_router
from api.routers import search as search_router

ensure_dirs()

app = FastAPI(title="OCRR Invoice API")

app.include_router(ksef_router.router)
app.include_router(inne_router.router)
app.include_router(euro_router.router)
app.include_router(search_router.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "source_dir": str(SOURCE_DIR),
        "source_dir_exists": SOURCE_DIR.exists(),
    }


# Statyczny frontend (bez builda) — musi być zamontowany na końcu, żeby nie
# przechwycił ścieżek /api/* i /health zadeklarowanych wyżej.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
