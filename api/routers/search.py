from fastapi import APIRouter

from utils import database_manager as db
from api.schemas import SearchResult, DuplicateMatch

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search(numer: str = "", kontrahent: str = ""):
    """
    Ręczne wyszukiwanie w obu tabelach SQL po numerze faktury i/lub
    kontrahencie, niezależnie od tego, jaka faktura jest aktualnie
    przeglądana albo w jakim jest przepływie (KSeF/inne/EURO).
    """
    return db.search_invoices(numer, kontrahent)


@router.get("/duplicates", response_model=list[DuplicateMatch])
def duplicates(numer: str = ""):
    """
    Sprawdzenie duplikatu na żądanie — używane przez frontend, gdy operator
    ręcznie poprawi numer faktury w formularzu (patrz app.js: blur na polu
    invoice_number). analyze_ksef/analyze_inne/analyze_euro sprawdzają
    duplikat tylko raz, na numerze odczytanym przez OCR przy otwarciu
    faktury — bez tego endpointu ręcznie wpisany numer nigdy nie byłby
    sprawdzony, co jest częste przy fakturach spoza KSeF (gorzej rozpoznawane
    przez OCR).
    """
    return db.find_duplicates(numer)
