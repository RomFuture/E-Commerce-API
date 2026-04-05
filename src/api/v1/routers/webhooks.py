import stripe
from fastapi import APIRouter, HTTPException, Request, status

from src.api.dependencies import DbSession, SettingsDep
from src.application.stripe_webhook_service import process_checkout_webhook_event
from src.domain.ecommerce_rules import DomainError

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request, db: DbSession, settings: SettingsDep) -> dict[str, bool]:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from e
    except stripe.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        ) from None

    try:
        process_checkout_webhook_event(db, event)
    except DomainError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook could not be applied",
        ) from None

    return {"received": True}
