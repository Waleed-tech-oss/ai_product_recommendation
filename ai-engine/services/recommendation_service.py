import numpy as np
from database.postgres import (
    get_product_by_id,
    get_similar_candidate_products,
    get_all_shopify_products
)

# ----------------------------------------
# Cosine Similarity
# ----------------------------------------

def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    return np.dot(vec1, vec2) / (
        np.linalg.norm(vec1) * np.linalg.norm(vec2)
    )


# ----------------------------------------
# Search Recommendations (Current)
# ----------------------------------------

def find_similar_products(query_embedding, products, top_k=5):

    similarities = []

    for product in products:

        embedding = product.get("embedding")

        if not embedding:
            continue

        score = cosine_similarity(
            query_embedding,
            embedding
        )

        similarities.append({

            "id": str(product["id"]),
            "shopify_id": product.get("shopify_id"),
            "title": product.get("title"),
            "handle": product.get("handle"),
            "vendor": product.get("vendor"),
            "product_type": product.get("product_type"),
            "image_url": product.get("image_url"),
            "sku": product.get("sku"),
            "price": product.get("price"),

            "score": round(float(score), 4)

        })

    similarities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return similarities[:top_k]
# ----------------------------------------
# More Like This (Hybrid AI Recommendation)
# ----------------------------------------

def get_more_like_this(product_id, top_k=6):

    current_product = get_product_by_id(product_id)

    if not current_product:
        return []

    current_embedding = current_product.get("embedding")

    if not current_embedding:
        return []

    products = get_similar_candidate_products(
        category=current_product["category"],
        article_type=current_product["articleType"],
        gender=current_product.get("gender")
    )

    similarities = []

    for product in products:

        # Skip current product
        if product["_id"] == current_product["_id"]:
            continue

        embedding = product.get("embedding")

        if not embedding:
            continue

        

        # -----------------------------
        # Base CLIP Score
        # -----------------------------

        clip_score = cosine_similarity(
            current_embedding,
            embedding
        )

        final_score = clip_score * 0.80

        reasons = []

        reasons.append("Similar visual appearance")

        # -----------------------------
        # Same Color
        # -----------------------------

        if (
            current_product.get("color")
            and product.get("color")
            and current_product["color"].lower()
            == product["color"].lower()
        ):
            final_score += 0.05
            reasons.append("Same color")

        # -----------------------------
        # Same Season
        # -----------------------------

        if (
            current_product.get("season")
            and product.get("season")
            and current_product["season"].lower()
            == product["season"].lower()
        ):
            final_score += 0.03
            reasons.append("Suitable for the same season")

        # -----------------------------
        # Same Usage
        # -----------------------------

        if (
            current_product.get("usage")
            and product.get("usage")
            and current_product["usage"].lower()
            == product["usage"].lower()
        ):
            final_score += 0.02
            reasons.append("Designed for the same usage")

        similarities.append({

            "id": str(product["_id"]),
            "name": product.get("name"),
            "description": product.get("description"),
            "category": product.get("category"),
            "subCategory": product.get("subCategory"),
            "articleType": product.get("articleType"),
            "gender": product.get("gender"),
            "color": product.get("color"),
            "season": product.get("season"),
            "usage": product.get("usage"),
            "image": product.get("image"),
            "price": product.get("price"),

            "clipScore": round(float(clip_score), 4),
            "score": round(float(final_score), 4),

            "isMoreLikeThis": True,

            "reason": ", ".join(reasons)

        })

    similarities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return similarities[:top_k]




# ----------------------------------------
# Shopify Image Recommendation
# ----------------------------------------

def find_similar_shopify_products(query_embedding, top_k=5):

    products = get_all_shopify_products()

    similarities = []

    for product in products:

        embedding = product.get("embedding")

        if not embedding:
            continue

        score = cosine_similarity(
            query_embedding,
            embedding
        )

        similarities.append({

            "id": product["id"],
            "shopify_id": product["shopify_id"],
            "title": product["title"],
            "handle": product["handle"],
            "vendor": product["vendor"],
            "product_type": product["product_type"],
            "image_url": product["image_url"],
            "sku": product["sku"],
            "price": product["price"],

            "score": round(float(score), 4)

        })

    similarities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return similarities[:top_k]

    