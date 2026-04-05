from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.domain.ecommerce_rules import validate_product_price_and_stock
from src.infrastructure.db.models.product import Product


def _public_product_where(
    *,
    q: str | None,
    min_price: Decimal | None,
    max_price: Decimal | None,
):
    conditions = [Product.is_active.is_(True)]
    if q and (term := q.strip()):
        conditions.append(Product.name.ilike(f"%{term}%"))
    if min_price is not None:
        conditions.append(Product.price >= min_price)
    if max_price is not None:
        conditions.append(Product.price <= max_price)
    return and_(*conditions)


def list_public_products(
    db: Session,
    *,
    q: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Product], int]:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    where_clause = _public_product_where(q=q, min_price=min_price, max_price=max_price)
    total = db.scalar(select(func.count()).select_from(Product).where(where_clause)) or 0
    rows = db.scalars(
        select(Product).where(where_clause).order_by(Product.id).limit(limit).offset(offset),
    ).all()
    return list(rows), int(total)


def get_public_product(db: Session, product_id: int) -> Product | None:
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        return None
    return product


def create_product(
    db: Session,
    *,
    name: str,
    description: str | None,
    price: Decimal,
    stock_quantity: int,
    is_active: bool = True,
) -> Product:
    validate_product_price_and_stock(price=price, stock_quantity=stock_quantity)
    product = Product(
        name=name.strip(),
        description=description,
        price=price,
        stock_quantity=stock_quantity,
        is_active=is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, fields: dict) -> Product | None:
    product = db.get(Product, product_id)
    if product is None:
        return None
    if "name" in fields:
        product.name = fields["name"].strip()
    if "description" in fields:
        product.description = fields["description"]
    if "price" in fields:
        product.price = fields["price"]
    if "stock_quantity" in fields:
        product.stock_quantity = fields["stock_quantity"]
    if "is_active" in fields:
        product.is_active = fields["is_active"]
    validate_product_price_and_stock(price=product.price, stock_quantity=product.stock_quantity)
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> bool:
    product = db.get(Product, product_id)
    if product is None:
        return False
    db.delete(product)
    db.commit()
    return True
