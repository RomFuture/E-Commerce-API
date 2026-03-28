from fastapi import APIRouter

from src.api.v1.routers import admin, auth, cart, products

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(products.router, prefix="/products", tags=["products"])
api_v1_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_v1_router.include_router(admin.router, prefix="/admin", tags=["admin"])
