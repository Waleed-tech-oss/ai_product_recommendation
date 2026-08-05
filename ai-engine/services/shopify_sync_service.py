import os
import re
from html import unescape

from database.postgres import ensure_shopify_search_schema, save_shopify_product
from services.clip_service import (
    generate_image_embedding,
    generate_product_text_embedding,
)
from utils.image_downloader import download_image


def _plain_text(value):
    text = unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return " ".join(text.split())


def build_search_document(product) -> str:
    category = product.category
    collections = product.collections or []
    variants = product.variants or []

    variant_options = []
    for variant in variants:
        for option in variant.selectedOptions or []:
            variant_options.extend([option.name, option.value])

    parts = [
        product.title,
        product.productType,
        product.vendor,
        product.description,
        category.fullName if category else None,
        category.name if category else None,
        " ".join(product.tags or []),
        " ".join(collection.title for collection in collections),
        " ".join(str(value or "") for value in variant_options),
    ]

    return " | ".join(
        " ".join(str(part).strip().split())
        for part in parts
        if part and str(part).strip()
    )


def sync_shopify_products(products):
    ensure_shopify_search_schema()
    synced_products = []
    failed_products = []

    for product in products:
        image_path = None

        try:
            print(f"\nProcessing: {product.title}")
            search_document = build_search_document(product)
            text_embedding = generate_product_text_embedding(search_document)

            image_embedding = None
            if product.imageUrl:
                image_path = download_image(product.imageUrl)
                image_embedding = generate_image_embedding(image_path)

            category = product.category
            variants = [variant.model_dump() for variant in (product.variants or [])]
            collections = [collection.model_dump() for collection in (product.collections or [])]

            save_shopify_product(
                shopify_id=product.shopifyId,
                shop_domain=product.shopDomain,
                title=product.title,
                handle=product.handle,
                vendor=product.vendor,
                product_type=product.productType,
                description=product.description,
                description_html=product.descriptionHtml,
                tags=product.tags,
                collections=collections,
                taxonomy_category_id=category.id if category else None,
                taxonomy_category_name=category.name if category else None,
                taxonomy_category_full_name=category.fullName if category else None,
                image_url=product.imageUrl,
                image_alt_text=product.imageAltText,
                sku=product.sku,
                price=product.price,
                currency_code=product.currencyCode,
                available_for_sale=product.availableForSale,
                created_at=product.createdAt,
                updated_at=product.updatedAt,
                image_embedding=image_embedding,
                text_embedding=text_embedding,
                search_document=search_document,
                variants=variants,
                embedding=image_embedding,
            )

            synced_products.append({
                "shopifyId": product.shopifyId,
                "title": product.title,
                "hasImageEmbedding": image_embedding is not None,
                "textEmbeddingLength": len(text_embedding),
            })

            print("✅ Saved enriched product to PostgreSQL")

        except Exception as error:
            print(f"❌ Failed: {product.title}: {error}")
            failed_products.append({"shopifyId": product.shopifyId, "title": product.title, "error": str(error)})

        finally:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

    return {
        "success": len(failed_products) == 0,
        "totalProducts": len(products),
        "syncedProducts": len(synced_products),
        "failedProducts": len(failed_products),
        "products": synced_products,
        "failures": failed_products,
    }
