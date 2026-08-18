from config import config_manager as cfg
from utils import database_manager as db
import payment_manager as pm
import mail_sender
from core import monthly_report


def get_policy() -> dict:
    conf = cfg.load_settings().get("email_config", {})
    return {
        "days_window": conf.get("days_window", 7),
        "recipients": conf.get("recipients", []),
        "owner_recipients": conf.get("owner_recipients", []),
    }


def save_policy(days_window: int, recipients: list, owner_recipients: list) -> dict:
    settings = cfg.load_settings()
    settings.setdefault("email_config", {})
    settings["email_config"]["days_window"] = days_window
    settings["email_config"]["recipients"] = recipients
    settings["email_config"]["owner_recipients"] = owner_recipients
    cfg.save_settings(settings)
    return get_policy()


def get_pending(days_window: int | None = None) -> list:
    """Faktury, które kwalifikowałyby się do wysyłki wg polityki (albo
    przekazanego wprost okna dni, do podglądu "co by było gdyby")."""
    if days_window is None:
        days_window = get_policy()["days_window"]
    payments, _ = pm.load_upcoming_payments_from_sql(days_window=days_window)
    return payments


def get_history(limit: int = 50) -> list:
    return db.get_sent_history(limit)


def send_selected(ids: list) -> dict:
    return mail_sender.send_by_ids(ids)


def get_monthly_preview(year: int, month: int) -> dict:
    return monthly_report.build_preview(year, month)


def send_monthly_report(year: int, month: int) -> dict:
    return monthly_report.send_monthly_package(year, month)


def get_owner_preview(year: int, month: int) -> dict:
    return monthly_report.build_owner_preview(year, month)


def send_owner_report(year: int, month: int) -> dict:
    return monthly_report.send_owner_report(year, month)


def get_dzialy(year_from: int, month_from: int, year_to: int, month_to: int) -> list:
    return monthly_report.list_dzialy(year_from, month_from, year_to, month_to)


def get_kontrahenci(year_from: int, month_from: int, year_to: int, month_to: int) -> list:
    return monthly_report.list_kontrahenci(year_from, month_from, year_to, month_to)


def get_dzial_preview(year_from: int, month_from: int, year_to: int, month_to: int,
                       dzial: str, with_pdfs: bool) -> dict:
    return monthly_report.build_dzial_preview(year_from, month_from, year_to, month_to, dzial, with_pdfs)


def send_dzial_report(year_from: int, month_from: int, year_to: int, month_to: int,
                       dzial: str, recipients: list, with_pdfs: bool) -> dict:
    return monthly_report.send_dzial_report(year_from, month_from, year_to, month_to, dzial, recipients, with_pdfs)


def get_kontrahent_preview(year_from: int, month_from: int, year_to: int, month_to: int,
                            kontrahent: str, with_pdfs: bool) -> dict:
    return monthly_report.build_kontrahent_preview(year_from, month_from, year_to, month_to, kontrahent, with_pdfs)


def send_kontrahent_report(year_from: int, month_from: int, year_to: int, month_to: int,
                            kontrahent: str, recipients: list, with_pdfs: bool) -> dict:
    return monthly_report.send_kontrahent_report(
        year_from, month_from, year_to, month_to, kontrahent, recipients, with_pdfs,
    )
