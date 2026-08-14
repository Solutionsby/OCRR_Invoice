import os
import platform
from pathlib import Path

from config import config_manager as cfg

DEFAULT_FOLDERS = {
    "ksef_source": "faktury_surowe",
    "inne_source": "faktury_surowe/inne",
    "euro_source": "faktury_surowe/euro",
    "dest": "faktury_przetworzone",
}

# Foldery ignorowane w przeglądarce podfolderów (UI wyboru folderów) — szum
# niezwiązany z fakturami, który i tak nie powinien być wybierany jako
# źródło/cel.
_BROWSE_IGNORE = {".git", "venv", "__pycache__", "node_modules"}


def get_base_path() -> Path:
    """
    Katalog zamontowany do kontenera (root, w którym operator wybiera
    podfoldery). W kontenerze Dockera ustawiamy INVOICES_BASE_PATH (np.
    /data) i to ma pierwszeństwo — wewnątrz kontenera platform.system()
    zawsze zwróci 'Linux', więc dotychczasowe rozróżnienie Windows/Mac by tam
    nie zadziałało. Poza Dockerem (zwykłe CLI na Macu/Windowsie) zmienna nie
    jest ustawiona i używana jest dotychczasowa logika. To jedyny poziom,
    który wymaga zmiany w docker-compose.yml/.env (HOST_DATA_DIR) przy
    przenosinach na nowy komputer — wszystko poniżej wybiera się z UI.
    """
    env_path = os.getenv("INVOICES_BASE_PATH")
    if env_path:
        return Path(env_path)
    if platform.system() == "Windows":
        return Path(r"Z:\Twoje_Faktury")
    return Path("./")


BASE_PATH = get_base_path()


def get_folders() -> dict:
    """
    Bieżące przypisania ról folderów (ścieżki względem BASE_PATH), z
    settings.json — czytane na bieżąco (nie raz przy starcie), żeby zmiana w
    UI działała bez restartu kontenera. Brakujące klucze wracają do
    dzisiejszych domyślnych ścieżek.
    """
    settings = cfg.load_settings()
    saved = settings.get("folders", {})
    return {**DEFAULT_FOLDERS, **saved}


def save_folders(folders: dict) -> dict:
    for key, relative in folders.items():
        _resolve(relative)  # rzuci ValueError, jeśli ścieżka wychodzi poza BASE_PATH
    settings = cfg.load_settings()
    settings["folders"] = {**get_folders(), **folders}
    cfg.save_settings(settings)
    return get_folders()


def _resolve(relative: str) -> Path:
    """Ścieżka względna wobec BASE_PATH, z zabezpieczeniem przed wyjściem poza
    zamontowany katalog (np. przez "../../etc")."""
    base_resolved = BASE_PATH.resolve()
    candidate = (BASE_PATH / relative).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise ValueError(f"Ścieżka '{relative}' wychodzi poza zamontowany katalog.")
    return candidate


def source_dir_ksef() -> Path:
    return _resolve(get_folders()["ksef_source"])


def source_dir_inne() -> Path:
    return _resolve(get_folders()["inne_source"])


def source_dir_euro() -> Path:
    return _resolve(get_folders()["euro_source"])


def dest_dir() -> Path:
    return _resolve(get_folders()["dest"])


def payment_dir() -> Path:
    return dest_dir() / "do_zaplaty"


def manual_dir() -> Path:
    return payment_dir() / "do_wpisania_recznie"


def manual_pay_dir() -> Path:
    return manual_dir() / "do_zaplaty"


def ensure_dirs() -> None:
    for d in (
        source_dir_ksef(), source_dir_inne(), source_dir_euro(),
        dest_dir(), payment_dir(), manual_pay_dir(),
    ):
        d.mkdir(parents=True, exist_ok=True)


def get_folders_resolved() -> list:
    """
    Bieżące przypisania ról jako lista (rola, ścieżka względna, ścieżka
    bezwzględna, czy istnieje) — kształt gotowy do wyświetlenia w UI wyboru
    folderów, żeby logika rozwiązywania ścieżek zostawała w jednym miejscu.
    """
    result = []
    for role, relative in get_folders().items():
        try:
            absolute = _resolve(relative)
            result.append({
                "role": role,
                "relative_path": relative,
                "absolute_path": str(absolute),
                "exists": absolute.is_dir(),
            })
        except ValueError:
            result.append({
                "role": role,
                "relative_path": relative,
                "absolute_path": None,
                "exists": False,
            })
    return result


def list_subfolders(relative: str = "") -> list:
    """Bezpośrednie podfoldery BASE_PATH/relative — dla przeglądarki folderów
    w UI wyboru źródeł/celu. Filtruje szum (.git, venv, katalogi kropkowane)."""
    target = _resolve(relative) if relative else BASE_PATH.resolve()
    if not target.is_dir():
        return []
    return sorted(
        p.name for p in target.iterdir()
        if p.is_dir() and p.name not in _BROWSE_IGNORE and not p.name.startswith(".")
    )
