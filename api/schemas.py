from pydantic import BaseModel


class InvoiceListItem(BaseModel):
    id: str
    file_name: str


class InvoiceProposal(BaseModel):
    id: str
    file_name: str
    scanned_firm: str
    firm_name: str
    invoice_number: str
    invoice_date: str
    payment_date: str
    payment_status: str
    payment_status_ambiguous: bool
    payment_form: str
    brutto: float
    kategoria: str = ""


class FinalizeRequest(BaseModel):
    firm_name: str
    invoice_number: str
    invoice_date: str
    payment_date: str
    payment_status: str
    payment_form: str
    brutto: float
    kategoria: str = ""
    scanned_firm: str
    # "t" — akceptacja (odpowiednik dawnego confirm == 't'/'n' w main.py)
    # "k" — kolejkuj do wpisania ręcznego (dawny tryb błyskawiczny 'k':
    #       trafia do do_zaplaty/do_wpisania_recznie, bez nauki bazy wiedzy)
    action: str


class FinalizeResult(BaseModel):
    target_path: str
    saved_to_payments: bool
