from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import DbSession, SettingsDep
from src.api.v1.deps.auth import CurrentUser
from src.api.v1.schemas.checkout import CheckoutSessionOut
from src.application.checkout_service import CheckoutError, start_checkout_from_cart

router = APIRouter()


@router.post("", response_model=CheckoutSessionOut)
def create_checkout_session(
    user: CurrentUser, db: DbSession, settings: SettingsDep
) -> CheckoutSessionOut:
    try:
        started = start_checkout_from_cart(db, user.id, settings)
    except CheckoutError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return CheckoutSessionOut(order_id=started.order_id, checkout_url=started.checkout_url)
