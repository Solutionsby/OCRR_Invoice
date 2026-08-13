from fastapi import FastAPI

from core.paths import SOURCE_DIR

app = FastAPI(title="OCRR Invoice API")


@app.get("/health")
def health():
    """
    Tymczasowy placeholder na Etap 0 — potwierdza, że kontener wstaje i widzi
    zamontowany folder źródłowy. Routery ksef/inne/euro dochodzą w Etapie 2+.
    """
    return {
        "status": "ok",
        "source_dir": str(SOURCE_DIR),
        "source_dir_exists": SOURCE_DIR.exists(),
    }
