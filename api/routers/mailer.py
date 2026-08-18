from fastapi import APIRouter

from core import mailer
from api.schemas import (
    MailerPolicy, PendingPayment, SentPayment, SendRequest, SendResult,
    MonthlyPreview, MonthlySendRequest, MonthlySendResult,
    OwnerPreview, OwnerSendResult,
    DzialPreview, DzialSendRequest, KontrahentPreview, KontrahentSendRequest,
)

router = APIRouter(prefix="/api/mailer", tags=["mailer"])


@router.get("/policy", response_model=MailerPolicy)
def get_policy():
    return mailer.get_policy()


@router.put("/policy", response_model=MailerPolicy)
def save_policy(body: MailerPolicy):
    return mailer.save_policy(body.days_window, body.recipients, body.owner_recipients)


@router.get("/pending", response_model=list[PendingPayment])
def get_pending(days_window: int | None = None):
    return mailer.get_pending(days_window)


@router.get("/history", response_model=list[SentPayment])
def get_history(limit: int = 50):
    return mailer.get_history(limit)


@router.post("/send", response_model=SendResult)
def send(body: SendRequest):
    return mailer.send_selected(body.ids)


@router.get("/monthly/preview", response_model=MonthlyPreview)
def monthly_preview(year: int, month: int):
    return mailer.get_monthly_preview(year, month)


@router.post("/monthly/send", response_model=MonthlySendResult)
def monthly_send(body: MonthlySendRequest):
    return mailer.send_monthly_report(body.year, body.month)


@router.get("/monthly/owner-preview", response_model=OwnerPreview)
def owner_preview(year: int, month: int):
    return mailer.get_owner_preview(year, month)


@router.post("/monthly/owner-send", response_model=OwnerSendResult)
def owner_send(body: MonthlySendRequest):
    return mailer.send_owner_report(body.year, body.month)


@router.get("/monthly/dzialy", response_model=list[str])
def dzialy(year_from: int, month_from: int, year_to: int, month_to: int):
    return mailer.get_dzialy(year_from, month_from, year_to, month_to)


@router.get("/monthly/kontrahenci", response_model=list[str])
def kontrahenci(year_from: int, month_from: int, year_to: int, month_to: int):
    return mailer.get_kontrahenci(year_from, month_from, year_to, month_to)


@router.get("/monthly/dzial-preview", response_model=DzialPreview)
def dzial_preview(year_from: int, month_from: int, year_to: int, month_to: int, dzial: str, with_pdfs: bool = True):
    return mailer.get_dzial_preview(year_from, month_from, year_to, month_to, dzial, with_pdfs)


@router.post("/monthly/dzial-send", response_model=MonthlySendResult)
def dzial_send(body: DzialSendRequest):
    return mailer.send_dzial_report(
        body.year_from, body.month_from, body.year_to, body.month_to,
        body.dzial, body.recipients, body.with_pdfs,
    )


@router.get("/monthly/kontrahent-preview", response_model=KontrahentPreview)
def kontrahent_preview(year_from: int, month_from: int, year_to: int, month_to: int,
                        kontrahent: str, with_pdfs: bool = True):
    return mailer.get_kontrahent_preview(year_from, month_from, year_to, month_to, kontrahent, with_pdfs)


@router.post("/monthly/kontrahent-send", response_model=MonthlySendResult)
def kontrahent_send(body: KontrahentSendRequest):
    return mailer.send_kontrahent_report(
        body.year_from, body.month_from, body.year_to, body.month_to,
        body.kontrahent, body.recipients, body.with_pdfs,
    )
