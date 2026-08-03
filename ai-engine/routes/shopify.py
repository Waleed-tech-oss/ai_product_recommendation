from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from services.shopify_sync_service import sync_shopify_products

router = APIRouter()


# ----------------------------------------
# Shopify Product Model
# ----------------------------------------

class ShopifyProduct(BaseModel):
    shopifyId: str
    title: str
    handle: str
    vendor: Optional[str] = None
    productType: Optional[str] = None
    imageUrl: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[str] = None


# ----------------------------------------
# Shopify Product Sync
# ----------------------------------------

@router.post("/sync-products")
async def sync_products(products: List[ShopifyProduct]):

    result = sync_shopify_products(products)

    return result