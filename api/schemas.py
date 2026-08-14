from pydantic import BaseModel


class InvoiceListItem(BaseModel):
    id: str
    file_name: str


class DuplicateMatch(BaseModel):
    tabela: str
    kontrahent: str
    plik: str | None = None


class SearchResult(BaseModel):
    tabela: str
    numer_faktury: str
    kontrahent: str
    data: str | None = None
    kwota: float | None = None
    plik: str | None = None
    wyslano: bool | None = None


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
    duplicate_matches: list[DuplicateMatch] = []


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


class InvoiceProposalInne(BaseModel):
    id: str
    file_name: str
    firm_name: str
    invoice_number: str
    invoice_date: str
    payment_date: str
    dzial: str
    kategoria: str
    dzial_known: bool
    netto: float
    vat: float
    brutto: float
    source: str
    duplicate_matches: list[DuplicateMatch] = []


class FinalizeRequestInne(BaseModel):
    firm_name: str
    invoice_number: str
    invoice_date: str
    payment_date: str
    dzial: str
    kategoria: str = ""
    oplacona: bool
    netto: float
    vat: float
    # "t" — akceptacja | "n" — po korekcie. Tryb "k" (kolejkuj do wpisania
    # ręcznego) nie istnieje w tym przepływie — brutto nie jest przyjmowane
    # tu wprost, zawsze przeliczane server-side jako netto+vat.
    action: str


class InvoiceProposalEuro(BaseModel):
    id: str
    file_name: str
    firm_name: str
    invoice_number: str
    invoice_date: str
    payment_date: str
    eur_netto: float
    eur_vat: float
    eur_brutto: float
    source: str
    suggested_rate: float | None
    rate_date: str | None
    dzial: str
    kategoria: str
    dzial_known: bool
    duplicate_matches: list[DuplicateMatch] = []


class FinalizeRequestEuro(BaseModel):
    firm_name: str
    invoice_number: str
    invoice_date: str
    payment_date: str
    dzial: str
    kategoria: str = ""
    oplacona: bool
    netto: float  # już przeliczone na PLN
    vat: float  # już przeliczone na PLN
    eur_netto: float
    eur_vat: float
    kurs_eur: float
    action: str


class MailerPolicy(BaseModel):
    days_window: int
    recipients: list[str]


class PendingPayment(BaseModel):
    id: int
    firm_name: str
    invoice_number: str
    payment_date: str
    brutto: float
    file_name: str | None = None


class SentPayment(BaseModel):
    firm_name: str
    invoice_number: str
    brutto: float
    sent_at: str | None = None


class SendRequest(BaseModel):
    ids: list[int]


class SendResult(BaseModel):
    sent: bool
    count: int
    recipients: list[str]
    missing_files: list[str]
    error: str | None = None


class FolderConfig(BaseModel):
    ksef_source: str
    inne_source: str
    euro_source: str
    dest: str


class FolderRole(BaseModel):
    role: str
    relative_path: str
    absolute_path: str | None
    exists: bool


class BrowseResult(BaseModel):
    path: str
    parent: str | None
    subfolders: list[str]
