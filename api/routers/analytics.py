from fastapi import APIRouter

from core import analytics
from api.schemas import (
    SpendTrendResponse, KontrahentRankResponse, DzialTrendResponse,
    KategoriaBreakdownResponse, PodkategoriaBreakdownResponse, SpendForecastResponse,
    DochodResponse,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/trend", response_model=SpendTrendResponse)
def trend(year_from: int, month_from: int, year_to: int, month_to: int, cykliczna: bool | None = None):
    return analytics.get_spend_trend(year_from, month_from, year_to, month_to, cykliczna)


@router.get("/forecast", response_model=SpendForecastResponse)
def forecast(months_ahead: int = 3, cykliczna: bool | None = None):
    return analytics.get_spend_forecast(months_ahead, cykliczna)


@router.get("/kontrahenci", response_model=KontrahentRankResponse)
def kontrahenci(year_from: int, month_from: int, year_to: int, month_to: int,
                 limit: int = 15, dzial: str | None = None):
    return analytics.get_top_kontrahenci(year_from, month_from, year_to, month_to, limit, dzial)


@router.get("/dzialy-trend", response_model=DzialTrendResponse)
def dzialy_trend(year_from: int, month_from: int, year_to: int, month_to: int):
    return analytics.get_dzial_trend(year_from, month_from, year_to, month_to)


@router.get("/kategorie", response_model=KategoriaBreakdownResponse)
def kategorie(year_from: int, month_from: int, year_to: int, month_to: int, dzial: str | None = None):
    return analytics.get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial)


@router.get("/podkategorie", response_model=PodkategoriaBreakdownResponse)
def podkategorie(year_from: int, month_from: int, year_to: int, month_to: int,
                  kategoria: str, dzial: str | None = None):
    return analytics.get_podkategoria_breakdown(year_from, month_from, year_to, month_to, kategoria, dzial)


@router.get("/dochod", response_model=DochodResponse)
def dochod(year_from: int, month_from: int, year_to: int, month_to: int):
    return analytics.get_dochod(year_from, month_from, year_to, month_to)
