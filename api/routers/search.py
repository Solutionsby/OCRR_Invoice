from fastapi import APIRouter

from utils import database_manager as db
from api.schemas import SearchResult

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search(numer: str = "", kontrahent: str = ""):
    """
    Ręczne wyszukiwanie w obu tabelach SQL po numerze faktury i/lub
    kontrahencie, niezależnie od tego, jaka faktura jest aktualnie
    przeglądana albo w jakim jest przepływie (KSeF/inne/EURO).
    """
    return db.search_invoices(numer, kontrahent)
