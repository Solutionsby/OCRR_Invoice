from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.paths import SOURCE_DIR
from core.ksef import analyze_ksef, finalize_ksef
from api.schemas import InvoiceListItem, InvoiceProposal, FinalizeRequest, FinalizeResult

router = APIRouter(prefix="/api/ksef", tags=["ksef"])


def _resolve_pdf(invoice_id: str) -> Path:
    """
    id faktury to zawsze sama nazwa pliku w SOURCE_DIR (bez podfolderów) —
    odrzucamy wszystko, co po odkodowaniu URL zawiera separator ścieżki albo
    ".."/"." jako cały komponent, żeby nie dało się wyjść poza ten folder.
    """
    name = unquote(invoice_id)
    if not name or Path(name).name != name:
        raise HTTPException(status_code=400, detail="Nieprawidłowe id faktury.")
    path = SOURCE_DIR / name
    if not path.exists() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Nie znaleziono faktury.")
    return path


@router.get("/invoices", response_model=list[InvoiceListItem])
def list_invoices():
    files = sorted(SOURCE_DIR.glob("*.pdf"))
    return [InvoiceListItem(id=f.name, file_name=f.name) for f in files]


@router.get("/invoices/{invoice_id}", response_model=InvoiceProposal)
def get_invoice(invoice_id: str):
    """
    Uruchamia analyze_ksef ponownie przy każdym wywołaniu — bezstanowe i
    bezpieczne do powtórzenia, bo nie ma żadnych efektów ubocznych aż do
    finalize (tak jak w main.py, gdzie ta sama ekstrakcja poprzedza
    interaktywną decyzję operatora).
    """
    path = _resolve_pdf(invoice_id)
    data = analyze_ksef(path)
    return InvoiceProposal(id=path.name, **data)


@router.get("/invoices/{invoice_id}/file")
def get_invoice_file(invoice_id: str):
    """
    content_disposition_type="inline" — bez tego Starlette domyślnie wysyła
    Content-Disposition: attachment, przez co przeglądarka próbuje pobrać PDF
    zamiast wyświetlić go w <iframe> podglądu.
    """
    path = _resolve_pdf(invoice_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.post("/invoices/{invoice_id}/finalize", response_model=FinalizeResult)
def finalize_invoice(invoice_id: str, body: FinalizeRequest):
    path = _resolve_pdf(invoice_id)
    data = body.model_dump()
    action = data.pop("action")
    result = finalize_ksef(path, data, action)
    return FinalizeResult(
        target_path=result["target_path"],
        saved_to_payments=result["saved_to_payments"],
    )
