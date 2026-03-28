from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import DbSession
from src.api.v1.schemas.product import ProductListResponse, ProductPublic
from src.application.product_service import get_public_product, list_public_products

router = APIRouter()


@router.get("", response_model=ProductListResponse)
def list_products(
    db: DbSession,
    q: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductListResponse:
    items, total = list_public_products(
        db,
        q=q,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(
        items=[ProductPublic.model_validate(p) for p in items],
        total=total,
    )


@router.get("/{product_id}", response_model=ProductPublic)
def get_product(product_id: int, db: DbSession) -> ProductPublic:
    product = get_public_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductPublic.model_validate(product)
