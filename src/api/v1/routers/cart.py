from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import DbSession
from src.api.v1.deps.auth import CurrentUser
from src.api.v1.schemas.cart import CartItemAdd, CartItemQuantityPatch, CartLineOut, CartOut
from src.application.cart_service import (
    CartError,
    CartSummary,
    add_cart_item,
    get_cart_summary,
    remove_cart_item,
    update_cart_item_quantity,
)
from src.domain.ecommerce_rules import DomainError

router = APIRouter()


def _to_cart_out(summary: CartSummary) -> CartOut:
    return CartOut(
        lines=[
            CartLineOut(
                product_id=line.product_id,
                name=line.name,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
            )
            for line in summary.lines
        ],
        line_count=summary.line_count,
        item_quantity_total=summary.item_quantity_total,
        subtotal=summary.subtotal,
    )


@router.get("", response_model=CartOut)
def get_cart(user: CurrentUser, db: DbSession) -> CartOut:
    return _to_cart_out(get_cart_summary(db, user.id))


@router.post("/items", response_model=CartOut, status_code=status.HTTP_200_OK)
def add_item(user: CurrentUser, db: DbSession, body: CartItemAdd) -> CartOut:
    try:
        summary = add_cart_item(
            db,
            user_id=user.id,
            product_id=body.product_id,
            quantity=body.quantity,
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except CartError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _to_cart_out(summary)


@router.patch("/items/{product_id}", response_model=CartOut)
def patch_item_quantity(
    product_id: int,
    user: CurrentUser,
    db: DbSession,
    body: CartItemQuantityPatch,
) -> CartOut:
    try:
        summary = update_cart_item_quantity(
            db,
            user_id=user.id,
            product_id=product_id,
            quantity=body.quantity,
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except CartError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart line not found")
    return _to_cart_out(summary)


@router.delete("/items/{product_id}", response_model=CartOut)
def delete_item(product_id: int, user: CurrentUser, db: DbSession) -> CartOut:
    summary = remove_cart_item(db, user_id=user.id, product_id=product_id)
    return _to_cart_out(summary)
