from fastapi import APIRouter

from core import analytics
from api.schemas import (
    SpendTrendResponse, KontrahentRankResponse, DzialTrendResponse,
    KategoriaBreakdownResponse, PodkategoriaBreakdownResponse, SpendForecastResponse,
    DochodResponse, DochodTrendResponse, DochodForecastResponse,
    DochodTrendTotalResponse, DochodForecastTotalResponse,
    BacktestItem, DochodBacktestResponse,
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
def kategorie(year_from: int, month_from: int, year_to: int, month_to: int,
              dzial: str | None = None, cykliczna: bool | None = None):
    return analytics.get_kategoria_breakdown(year_from, month_from, year_to, month_to, dzial, cykliczna)


@router.get("/podkategorie", response_model=PodkategoriaBreakdownResponse)
def podkategorie(year_from: int, month_from: int, year_to: int, month_to: int,
                  kategoria: str, dzial: str | None = None, cykliczna: bool | None = None):
    return analytics.get_podkategoria_breakdown(year_from, month_from, year_to, month_to, kategoria, dzial, cykliczna)


@router.get("/dochod", response_model=DochodResponse)
def dochod(year_from: int, month_from: int, year_to: int, month_to: int):
    return analytics.get_dochod(year_from, month_from, year_to, month_to)


@router.get("/dochod-trend", response_model=DochodTrendResponse)
def dochod_trend(dzial: str, year_from: int, month_from: int, year_to: int, month_to: int):
    return analytics.get_dochod_trend(dzial, year_from, month_from, year_to, month_to)


@router.get("/dochod-forecast", response_model=DochodForecastResponse)
def dochod_forecast(dzial: str, months_ahead: int = 3):
    return analytics.get_dochod_forecast(dzial, months_ahead)


@router.get("/dochod-trend-total", response_model=DochodTrendTotalResponse)
def dochod_trend_total(dzialy: str, year_from: int, month_from: int, year_to: int, month_to: int):
    return analytics.get_dochod_trend_total(dzialy.split(","), year_from, month_from, year_to, month_to)


@router.get("/dochod-forecast-total", response_model=DochodForecastTotalResponse)
def dochod_forecast_total(dzialy: str, months_ahead: int = 3):
    return analytics.get_dochod_forecast_total(dzialy.split(","), months_ahead)


@router.get("/forecast-backtest", response_model=list[BacktestItem])
def forecast_backtest(months_back: int = 6, cykliczna: bool | None = None):
    return analytics.get_spend_forecast_backtest(months_back, cykliczna)


@router.get("/dochod-backtest", response_model=DochodBacktestResponse)
def dochod_backtest(dzial: str, months_back: int = 6):
    return analytics.get_dochod_backtest(dzial, months_back)


@router.get("/dochod-backtest-total", response_model=DochodBacktestResponse)
def dochod_backtest_total(dzialy: str, months_back: int = 6):
    return analytics.get_dochod_backtest_total(dzialy.split(","), months_back)
