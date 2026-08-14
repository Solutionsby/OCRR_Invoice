from pathlib import Path
from urllib.parse import unquote

from fastapi import HTTPException


def resolve_pdf(source_dir: Path, invoice_id: str) -> Path:
    """
    Wspólna dla wszystkich przepływów (ksef/inne/euro) zamiana id (nazwy
    pliku) na ścieżkę wewnątrz source_dir — odrzuca wszystko, co po
    odkodowaniu URL zawiera separator ścieżki albo ".."/"." jako cały
    komponent, żeby nie dało się wyjść poza ten folder.
    """
    name = unquote(invoice_id)
    if not name or Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nieprawidłowe id faktury.")
    path = source_dir / name
    if not path.exists() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Nie znaleziono faktury.")
    return path
