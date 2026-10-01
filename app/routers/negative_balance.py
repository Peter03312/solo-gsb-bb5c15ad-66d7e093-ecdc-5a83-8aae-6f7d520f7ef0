"""GET /accounts/{account_id}/negative-balance-periods -- funding-gap windows."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..schemas import NegativeBalancePeriod, NegativeBalancePeriodsResponse
from ..services import negative_balance_periods
from .webhooks import get_db

router = APIRouter(tags=["negative-balance-periods"])


@router.get(
    "/accounts/{account_id}/negative-balance-periods",
    response_model=NegativeBalancePeriodsResponse,
)
def account_negative_balance_periods(
    account_id: str,
    currency: str = Query(..., min_length=3, max_length=3, description="ISO 4217 currency code"),
    start: datetime = Query(
        ..., description="Window start business time (inclusive, by occurred_at)"
    ),
    end: datetime = Query(
        ..., description="Window end business time (exclusive); must be later than start"
    ),
    db: Session = Depends(get_db),
):
    # Normalize to naive UTC to match stored occurred_at values.
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc).replace(tzinfo=None)
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be later than start")

    result = negative_balance_periods(db, account_id, currency.upper(), start, end)
    return NegativeBalancePeriodsResponse(
        account_id=result["account_id"],
        currency=result["currency"],
        window=result["window"],
        opening_balance=result["opening_balance"],
        gaps=[NegativeBalancePeriod(**g) for g in result["gaps"]],
    )
