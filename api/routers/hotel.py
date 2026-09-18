from fastapi import APIRouter, HTTPException

from core import hotel_analytics
from api.schemas import (
    HotelSalesTrendResponse, HotelSalesBreakdownResponse,
    HotelRecordsResponse, HotelDeleteResponse, HotelPaymentMethodsResponse,
)

router = APIRouter(prefix="/api/hotel", tags=["hotel"])


@router.get("/sales-trend", response_model=HotelSalesTrendResponse)
def sales_trend(year_from: int, month_from: int, year_to: int, month_to: int):
    return hotel_analytics.get_sales_trend(year_from, month_from, year_to, month_to)


@router.get("/sales-breakdown", response_model=HotelSalesBreakdownResponse)
def sales_breakdown(year_from: int, month_from: int, year_to: int, month_to: int):
    return hotel_analytics.get_sales_breakdown(year_from, month_from, year_to, month_to)


@router.get("/payment-methods", response_model=HotelPaymentMethodsResponse)
def payment_methods(year_from: int, month_from: int, year_to: int, month_to: int):
    return hotel_analytics.get_payment_methods(year_from, month_from, year_to, month_to)


@router.get("/records", response_model=HotelRecordsResponse)
def records(year_from: int, month_from: int, year_to: int, month_to: int):
    return hotel_analytics.get_records(year_from, month_from, year_to, month_to)


@router.delete("/records/{record_id}", response_model=HotelDeleteResponse)
def delete_record(record_id: str):
    if not hotel_analytics.delete_record(record_id):
        raise HTTPException(status_code=404, detail="Nie znaleziono rekordu")
    return {"status": "deleted"}
