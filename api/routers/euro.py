from fastapi import APIRouter
from fastapi.responses import FileResponse

from core.paths import source_dir_euro
from core.euro import analyze_euro, finalize_euro
from api.schemas import InvoiceListItem, InvoiceProposalEuro, FinalizeRequestEuro, FinalizeResult
from api.routers.common import resolve_pdf

router = APIRouter(prefix="/api/euro", tags=["euro"])


def _resolve_pdf(invoice_id: str):
    return resolve_pdf(source_dir_euro(), invoice_id)


@router.get("/invoices", response_model=list[InvoiceListItem])
def list_invoices():
    files = sorted(source_dir_euro().glob("*.pdf"))
    return [InvoiceListItem(id=f.name, file_name=f.name) for f in files]


@router.get("/invoices/{invoice_id}", response_model=InvoiceProposalEuro)
def get_invoice(invoice_id: str):
    path = _resolve_pdf(invoice_id)
    data = analyze_euro(path)
    return InvoiceProposalEuro(id=path.name, **data)


@router.get("/invoices/{invoice_id}/file")
def get_invoice_file(invoice_id: str):
    path = _resolve_pdf(invoice_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.post("/invoices/{invoice_id}/finalize", response_model=FinalizeResult)
def finalize_invoice(invoice_id: str, body: FinalizeRequestEuro):
    path = _resolve_pdf(invoice_id)
    data = body.model_dump()
    action = data.pop("action")
    result = finalize_euro(path, data, action)
    return FinalizeResult(
        target_path=result["target_path"],
        saved_to_payments=result["saved_to_payments"],
    )
