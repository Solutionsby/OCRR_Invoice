import os
import platform
from pathlib import Path


def get_base_path() -> Path:
    """
    Katalog bazowy z fakturami. W kontenerze Dockera ustawiamy
    INVOICES_BASE_PATH (np. /data) i to ma pierwszeństwo — wewnątrz
    kontenera platform.system() zawsze zwróci 'Linux', więc dotychczasowe
    rozróżnienie Windows/Mac by tam nie zadziałało. Poza Dockerem (zwykłe
    CLI na Macu/Windowsie) zmienna nie jest ustawiona i używana jest
    dotychczasowa logika.
    """
    env_path = os.getenv("INVOICES_BASE_PATH")
    if env_path:
        return Path(env_path)
    if platform.system() == "Windows":
        return Path(r"Z:\Twoje_Faktury")
    return Path("./")


BASE_PATH = get_base_path()
SOURCE_DIR = BASE_PATH / "faktury_surowe"
DEST_DIR = BASE_PATH / "faktury_przetworzone"
PAYMENT_DIR = DEST_DIR / "do_zaplaty"
MANUAL_DIR = PAYMENT_DIR / "do_wpisania_recznie"
MANUAL_PAY_DIR = MANUAL_DIR / "do_zaplaty"


def ensure_dirs() -> None:
    for d in (SOURCE_DIR, DEST_DIR, PAYMENT_DIR, MANUAL_PAY_DIR):
        d.mkdir(parents=True, exist_ok=True)
