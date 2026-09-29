"""GET /accounts/{account_id}/negative-balances -- locate funding gaps."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..schemas import NegativeBalancePeriod, NegativeBalanceResponse, to_decimal_str
from ..services import negative_balance_periods
from .webhooks import get_db

router = APIRouter(tags=["negative-balances"])


@router.get(
    "/accounts/{account_id}/negative-balances",
    response_model=NegativeBalanceResponse,
)
def account_negative_balances(
    account_id: str,
    currency: str = Query(
        ...,
        min_length=3,
        max_length=3,
        description="ISO-4217 currency code to inspect, e.g. USD",
    ),
    start: datetime = Query(
        ..., description="Window start (inclusive) by business time occurred_at"
    ),
    end: datetime = Query(
        ..., description="Window end (exclusive) by business time occurred_at"
    ),
    db: Session = Depends(get_db),
):
    currency = currency.upper()
    # Normalize to naive UTC to match stored occurred_at values.
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc).replace(tzinfo=None)
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be later than start")

    result = negative_balance_periods(db, account_id, currency, start, end)
    return NegativeBalanceResponse(
        account_id=result["account_id"],
        currency=result["currency"],
        window=result["window"],
        opening_balance=to_decimal_str(result["opening_balance"]),
        periods=[
            NegativeBalancePeriod(
                start=p["start"],
                recovered_at=p["recovered_at"],
                minimum_balance=to_decimal_str(p["minimum_balance"]),
            )
            for p in result["periods"]
        ],
    )
