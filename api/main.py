from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.paths import BASE_PATH, source_dir_ksef, source_dir_inne, source_dir_euro, dest_dir, ensure_dirs
from api.routers import ksef as ksef_router
from api.routers import inne as inne_router
from api.routers import euro as euro_router
from api.routers import search as search_router
from api.routers import mailer as mailer_router
from api.routers import folders as folders_router

ensure_dirs()

app = FastAPI(title="OCRR Invoice API")

app.include_router(ksef_router.router)
app.include_router(inne_router.router)
app.include_router(euro_router.router)
app.include_router(search_router.router)
app.include_router(mailer_router.router)
app.include_router(folders_router.router)


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
