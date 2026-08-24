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
    owner_recipients: list[str] = []


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


class MonthlyPreview(BaseModel):
    year: int
    month: int
    invoice_count: int
    total_brutto: float
    attachment_count: int
    attachments: list[str]


class MonthlySendRequest(BaseModel):
    year: int
    month: int


class MonthlySendResult(BaseModel):
    sent: bool
    count: int
    attachment_count: int
    recipients: list[str]
    missing_files: list[str]
    error: str | None = None


class DzialBreakdownItem(BaseModel):
    dzial: str
    count: int
    brutto: float


class OwnerPreview(BaseModel):
    year: int
    month: int
    invoice_count: int
    total_brutto: float
    breakdown: list[DzialBreakdownItem]


class OwnerSendResult(BaseModel):
    sent: bool
    count: int
    recipients: list[str]
    error: str | None = None


class DzialPreview(BaseModel):
    dzial: str
    invoice_count: int
    total_brutto: float
    attachment_count: int
    attachments: list[str]


class DzialSendRequest(BaseModel):
    year_from: int
    month_from: int
    year_to: int
    month_to: int
    dzial: str
    recipients: list[str]
    with_pdfs: bool = True


class KontrahentPreview(BaseModel):
    kontrahent: str
    invoice_count: int
    total_brutto: float
    attachment_count: int
    attachments: list[str]


class KontrahentSendRequest(BaseModel):
    year_from: int
    month_from: int
    year_to: int
    month_to: int
    kontrahent: str
    recipients: list[str]
    with_pdfs: bool = True


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


class SpendTrendPoint(BaseModel):
    year: int
    month: int
    netto: float
    vat: float
    brutto: float
    count: int


class SpendTrendResponse(BaseModel):
    points: list[SpendTrendPoint]
    total_netto: float
    total_vat: float
    total_brutto: float
    total_count: int


class KontrahentRankItem(BaseModel):
    kontrahent: str
    brutto: float
    count: int
    pct: float


class KontrahentRankResponse(BaseModel):
    items: list[KontrahentRankItem]
    total_brutto: float


class MonthLabel(BaseModel):
    year: int
    month: int


class DzialTrendSeries(BaseModel):
    dzial: str
    values: list[float]
    total: float


class DzialTrendResponse(BaseModel):
    months: list[MonthLabel]
    series: list[DzialTrendSeries]


class KategoriaBreakdownItem(BaseModel):
    kategoria: str
    brutto: float
    count: int
    pct: float


class KategoriaBreakdownResponse(BaseModel):
    items: list[KategoriaBreakdownItem]
    total_brutto: float


class PodkategoriaBreakdownItem(BaseModel):
    podkategoria: str
    brutto: float
    count: int
    pct: float


class PodkategoriaBreakdownResponse(BaseModel):
    items: list[PodkategoriaBreakdownItem]
    total_brutto: float


class ForecastPoint(BaseModel):
    year: int
    month: int
    brutto: float


class SpendForecastResponse(BaseModel):
    history: list[SpendTrendPoint]
    forecast: list[ForecastPoint]
    seasonal_index: dict[str, float]
    history_months: int
    level: float


class DochodItem(BaseModel):
    dzial: str
    koszt_netto: float
    przychod_netto: float | None
    dochod: float
    marza_pct: float | None


class DochodResponse(BaseModel):
    items: list[DochodItem]
    total_koszt_netto: float
    total_przychod_netto: float
    total_dochod: float
    total_marza_pct: float | None
    dzialy_bez_przychodu: list[str]


class DochodTrendYearSeries(BaseModel):
    year: int
    values: list[float | None]


class DochodTrendResponse(BaseModel):
    dzial: str
    years: list[int]
    koszt_by_year: list[DochodTrendYearSeries]
    przychod_by_year: list[DochodTrendYearSeries]
    dochod_by_year: list[DochodTrendYearSeries]


class ForecastValuePoint(BaseModel):
    year: int
    month: int
    value: float


class DochodForecastSeries(BaseModel):
    forecast: list[ForecastValuePoint]
    seasonal_index: dict[str, float]
    history_months: int
    level: float


class DochodForecastResponse(BaseModel):
    dzial: str
    przychod: DochodForecastSeries
    dochod: DochodForecastSeries


class DochodTrendTotalResponse(BaseModel):
    dzialy: list[str]
    years: list[int]
    koszt_by_year: list[DochodTrendYearSeries]
    przychod_by_year: list[DochodTrendYearSeries]
    dochod_by_year: list[DochodTrendYearSeries]


class DochodForecastTotalResponse(BaseModel):
    dzialy: list[str]
    przychod: DochodForecastSeries
    dochod: DochodForecastSeries


class BacktestItem(BaseModel):
    year: int
    month: int
    actual: float
    forecast: float
    diff: float
    diff_pct: float | None


class DochodBacktestResponse(BaseModel):
    dzial: str | None = None
    dzialy: list[str] | None = None
    przychod: list[BacktestItem]
    dochod: list[BacktestItem]
