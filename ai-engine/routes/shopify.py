from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.shopify_sync_service import sync_shopify_products


router = APIRouter(tags=["Shopify Catalog Sync"])


class ShopifyCollection(BaseModel):
    id: Optional[str] = None
    title: str
    handle: Optional[str] = None


class ShopifyCategory(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    fullName: Optional[str] = None


class ShopifySelectedOption(BaseModel):
    name: str
    value: str


class ShopifyVariant(BaseModel):
    id: str
    title: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[str] = None
    compareAtPrice: Optional[str] = None
    availableForSale: bool = False
    inventoryQuantity: Optional[int] = None
    selectedOptions: List[ShopifySelectedOption] = Field(default_factory=list)
    imageUrl: Optional[str] = None


class ShopifyProduct(BaseModel):
    shopifyId: str
    shopDomain: str = ""
    title: str
    handle: str
    vendor: Optional[str] = None
    productType: Optional[str] = None
    description: Optional[str] = None
    descriptionHtml: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    collections: List[ShopifyCollection] = Field(default_factory=list)
    category: Optional[ShopifyCategory] = None
    imageUrl: Optional[str] = None
    imageAltText: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[str] = None
    currencyCode: Optional[str] = None
    availableForSale: bool = False
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    variants: List[ShopifyVariant] = Field(default_factory=list)


@router.post("/sync-products")
async def sync_products(products: List[ShopifyProduct]):
    return sync_shopify_products(products)
