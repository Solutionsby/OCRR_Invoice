from fastapi import APIRouter
from fastapi.responses import FileResponse

from core.paths import source_dir_inne
from core.inne import analyze_inne, finalize_inne
from api.schemas import InvoiceListItem, InvoiceProposalInne, FinalizeRequestInne, FinalizeResult
from api.routers.common import resolve_pdf

router = APIRouter(prefix="/api/inne", tags=["inne"])


def _resolve_pdf(invoice_id: str):
    return resolve_pdf(source_dir_inne(), invoice_id)


@router.get("/invoices", response_model=list[InvoiceListItem])
def list_invoices():
    files = sorted(source_dir_inne().glob("*.pdf"))
    return [InvoiceListItem(id=f.name, file_name=f.name) for f in files]


@router.get("/invoices/{invoice_id}", response_model=InvoiceProposalInne)
def get_invoice(invoice_id: str):
    path = _resolve_pdf(invoice_id)
    data = analyze_inne(path)
    return InvoiceProposalInne(id=path.name, **data)


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
def finalize_invoice(invoice_id: str, body: FinalizeRequestInne):
    path = _resolve_pdf(invoice_id)
    data = body.model_dump()
    action = data.pop("action")
    result = finalize_inne(path, data, action)
    return FinalizeResult(
        target_path=result["target_path"],
        saved_to_payments=result["saved_to_payments"],
    )
