from fastapi import APIRouter, HTTPException, Response, status

from src.api.dependencies import DbSession
from src.api.v1.deps.auth import AdminUser
from src.api.v1.schemas.product import ProductAdminOut, ProductCreate, ProductUpdate
from src.application.product_service import create_product, delete_product, update_product
from src.domain.ecommerce_rules import DomainError
from src.infrastructure.db.models.product import Product

router = APIRouter()


@router.get("/health")
def admin_health(_admin: AdminUser) -> dict[str, bool]:
    return {"admin": True}


@router.post("/products", response_model=ProductAdminOut, status_code=status.HTTP_201_CREATED)
def admin_create_product(
    _admin: AdminUser,
    db: DbSession,
    body: ProductCreate,
) -> ProductAdminOut:
    try:
        product = create_product(
            db,
            name=body.name,
            description=body.description,
            price=body.price,
            stock_quantity=body.stock_quantity,
            is_active=body.is_active,
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ProductAdminOut.model_validate(product)


@router.patch("/products/{product_id}", response_model=ProductAdminOut)
def admin_update_product(
    product_id: int,
    _admin: AdminUser,
    db: DbSession,
    body: ProductUpdate,
) -> ProductAdminOut:
    data = body.model_dump(exclude_unset=True)
    if not data:
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return ProductAdminOut.model_validate(product)
    try:
        product = update_product(db, product_id, data)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductAdminOut.model_validate(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_product(product_id: int, _admin: AdminUser, db: DbSession) -> Response:
    if not delete_product(db, product_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
