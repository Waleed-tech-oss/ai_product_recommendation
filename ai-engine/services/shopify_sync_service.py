import os

from utils.image_downloader import download_image
from services.clip_service import generate_embedding
from database.postgres import save_shopify_product


def sync_shopify_products(products):

    synced_products = []

    for product in products:

        # Skip products without image
        if not product.imageUrl:
            print(f"Skipping {product.title} (No Image)")
            continue

        print(f"\nProcessing: {product.title}")

        # ----------------------------------------
        # Download Image
        # ----------------------------------------

        image_path = download_image(product.imageUrl)

        print(f"Downloaded: {image_path}")

        # ----------------------------------------
        # Generate CLIP Embedding
        # ----------------------------------------

        embedding = generate_embedding(image_path)

        print(f"Embedding Length: {len(embedding)}")

        # ----------------------------------------
        # Save Product in PostgreSQL
        # ----------------------------------------

        save_shopify_product(
            shopify_id=product.shopifyId,
            title=product.title,
            handle=product.handle,
            vendor=product.vendor,
            product_type=product.productType,
            image_url=product.imageUrl,
            sku=product.sku,
            price=product.price,
            embedding=embedding
        )

        print("✅ Saved to PostgreSQL")

        synced_products.append({
            "shopifyId": product.shopifyId,
            "title": product.title,
            "embeddingLength": len(embedding)
        })

        # ----------------------------------------
        # Delete Temporary Image
        # ----------------------------------------

        if os.path.exists(image_path):
            os.remove(image_path)

    return {
        "success": True,
        "totalProducts": len(synced_products),
        "products": synced_products
    }