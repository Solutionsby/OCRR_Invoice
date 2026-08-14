from config import config_manager as cfg
from utils import database_manager as db
import payment_manager as pm
import mail_sender


def get_policy() -> dict:
    conf = cfg.load_settings().get("email_config", {})
    return {
        "days_window": conf.get("days_window", 7),
        "recipients": conf.get("recipients", []),
    }


def save_policy(days_window: int, recipients: list) -> dict:
    settings = cfg.load_settings()
    settings.setdefault("email_config", {})
    settings["email_config"]["days_window"] = days_window
    settings["email_config"]["recipients"] = recipients
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
