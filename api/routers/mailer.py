from fastapi import APIRouter

from core import mailer
from api.schemas import (
    MailerPolicy, PendingPayment, SentPayment, SendRequest, SendResult,
)

router = APIRouter(prefix="/api/mailer", tags=["mailer"])


@router.get("/policy", response_model=MailerPolicy)
def get_policy():
    return mailer.get_policy()


@router.put("/policy", response_model=MailerPolicy)
def save_policy(body: MailerPolicy):
    return mailer.save_policy(body.days_window, body.recipients)


@router.get("/pending", response_model=list[PendingPayment])
def get_pending(days_window: int | None = None):
    return mailer.get_pending(days_window)


@router.get("/history", response_model=list[SentPayment])
def get_history(limit: int = 50):
    return mailer.get_history(limit)


@router.post("/send", response_model=SendResult)
def send(body: SendRequest):
    return mailer.send_selected(body.ids)
