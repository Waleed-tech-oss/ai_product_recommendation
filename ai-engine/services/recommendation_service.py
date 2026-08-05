from __future__ import annotations

import os
import re
from typing import Any

import numpy as np

from database.postgres import (
    get_all_shopify_products,
    get_product_by_id,
    get_similar_candidate_products,
)


def cosine_similarity(vec1, vec2) -> float:
    left = np.asarray(vec1, dtype=np.float32)
    right = np.asarray(vec2, dtype=np.float32)

    if left.ndim != 1 or right.ndim != 1 or left.shape != right.shape:
        return 0.0

    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    if denominator <= 1e-12:
        return 0.0

    return float(np.dot(left, right) / denominator)


def _read_float_setting(name, default, minimum=0.0, maximum=1.0):
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _normalise(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _product_text(product: dict[str, Any]) -> str:
    if product.get("search_document"):
        return str(product["search_document"])

    tags = product.get("tags") or []
    collections = product.get("collections") or []

    collection_titles = [
        item.get("title", "") if isinstance(item, dict) else str(item)
        for item in collections
    ]

    return " ".join(
        str(value or "")
        for value in [
            product.get("title"),
            product.get("product_type"),
            product.get("taxonomy_category_full_name"),
            product.get("vendor"),
            product.get("description"),
            " ".join(str(tag) for tag in tags),
            " ".join(collection_titles),
        ]
    )


def lexical_relevance(query_text: str | None, product: dict[str, Any]) -> float:
    query = _normalise(query_text)
    document = _normalise(_product_text(product))

    if not query or not document:
        return 0.0

    if query == _normalise(product.get("title")):
        return 1.0

    phrase_bonus = 0.35 if query in document else 0.0
    query_tokens = set(query.split())
    document_tokens = set(document.split())

    if not query_tokens:
        return phrase_bonus

    overlap = len(query_tokens & document_tokens) / len(query_tokens)
    return min(1.0, phrase_bonus + (overlap * 0.65))


def _shopify_product_result(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(product["id"]),
        "shopify_id": product.get("shopify_id"),
        "shop_domain": product.get("shop_domain"),
        "title": product.get("title"),
        "handle": product.get("handle"),
        "vendor": product.get("vendor"),
        "product_type": product.get("product_type"),
        "description": product.get("description"),
        "tags": product.get("tags") or [],
        "collections": product.get("collections") or [],
        "taxonomy_category_name": product.get("taxonomy_category_name"),
        "taxonomy_category_full_name": product.get("taxonomy_category_full_name"),
        "image_url": product.get("image_url"),
        "image_alt_text": product.get("image_alt_text"),
        "sku": product.get("sku"),
        "price": product.get("price"),
        "currency_code": product.get("currency_code"),
        "available_for_sale": product.get("available_for_sale"),
        "variants": product.get("variants") or [],
    }


def _normalized_product_type(value):
    return " ".join(str(value or "").strip().lower().split())


def find_similar_products(
    query_embedding,
    products,
    top_k=5,
    query_text: str | None = None,
):
    """Rank text searches using product text, keywords, and image fallback."""
    text_weight = _read_float_setting("TEXT_SEMANTIC_WEIGHT", 0.55)
    lexical_weight = _read_float_setting("LEXICAL_WEIGHT", 0.35)
    visual_weight = _read_float_setting("TEXT_TO_IMAGE_WEIGHT", 0.10)

    weight_sum = text_weight + lexical_weight + visual_weight
    if weight_sum <= 0:
        text_weight, lexical_weight, visual_weight, weight_sum = 0.55, 0.35, 0.10, 1.0

    text_weight /= weight_sum
    lexical_weight /= weight_sum
    visual_weight /= weight_sum

    ranked = []

    for product in products:
        text_embedding = product.get("text_embedding")
        image_embedding = product.get("image_embedding") or product.get("embedding")

        text_score = max(0.0, cosine_similarity(query_embedding, text_embedding)) if text_embedding else 0.0
        image_score = max(0.0, cosine_similarity(query_embedding, image_embedding)) if image_embedding else 0.0
        lexical_score = lexical_relevance(query_text, product)

        # Old records without text embeddings still work through image CLIP.
        if not text_embedding:
            effective_text_weight = 0.0
            effective_visual_weight = text_weight + visual_weight
        else:
            effective_text_weight = text_weight
            effective_visual_weight = visual_weight

        final_score = (
            text_score * effective_text_weight
            + lexical_score * lexical_weight
            + image_score * effective_visual_weight
        )

        result = _shopify_product_result(product)
        result.update({
            "textScore": round(text_score, 4),
            "lexicalScore": round(lexical_score, 4),
            "imageScore": round(image_score, 4),
            "score": round(max(0.0, final_score), 4),
            "rankingMode": "text_lexical_visual_hybrid",
        })
        ranked.append(result)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]


def _filter_visual_results(ranked_products, infer_product_type):
    if not ranked_products:
        return []

    top_result = ranked_products[0]
    top_score = float(top_result.get("score") or 0.0)
    minimum_score = _read_float_setting("MIN_VISUAL_RESULT_SCORE", 0.20)
    maximum_score_gap = _read_float_setting("MAX_VISUAL_SCORE_GAP", 0.12)
    cutoff = max(minimum_score, top_score - maximum_score_gap)

    filtered = [
        product for product in ranked_products
        if float(product.get("score") or 0.0) >= cutoff
    ]

    if not filtered:
        filtered = [top_result]

    if not infer_product_type:
        return filtered

    inferred_type = _normalized_product_type(top_result.get("product_type"))
    if not inferred_type:
        return filtered

    same_type = [
        product for product in filtered
        if _normalized_product_type(product.get("product_type")) == inferred_type
    ]

    if not same_type:
        return filtered

    for product in same_type:
        product["inferredProductType"] = top_result.get("product_type")

    return same_type


def find_hybrid_shopify_products(
    image_embedding,
    products,
    text_embedding=None,
    query_text: str | None = None,
    top_k=5,
    image_weight=None,
    infer_product_type=True,
):
    if image_weight is None:
        image_weight = _read_float_setting("HYBRID_IMAGE_WEIGHT", 0.65)

    image_weight = max(0.0, min(image_weight, 1.0))
    use_text = text_embedding is not None

    lexical_weight = _read_float_setting("HYBRID_LEXICAL_WEIGHT", 0.10) if use_text else 0.0
    text_weight = max(0.0, 1.0 - image_weight - lexical_weight) if use_text else 0.0

    ranked = []

    for product in products:
        product_image_embedding = product.get("image_embedding") or product.get("embedding")
        if not product_image_embedding:
            continue

        image_score = max(0.0, cosine_similarity(image_embedding, product_image_embedding))
        lexical_score = lexical_relevance(query_text, product) if use_text else 0.0

        product_text_embedding = product.get("text_embedding")
        text_score = (
            max(0.0, cosine_similarity(text_embedding, product_text_embedding))
            if use_text and product_text_embedding
            else 0.0
        )

        if use_text:
            final_score = (
                image_score * image_weight
                + text_score * text_weight
                + lexical_score * lexical_weight
            )
        else:
            final_score = image_score

        result = _shopify_product_result(product)
        result.update({
            "imageScore": round(image_score, 4),
            "textScore": round(text_score, 4) if use_text else None,
            "lexicalScore": round(lexical_score, 4) if use_text else None,
            "score": round(max(0.0, final_score), 4),
            "rankingMode": "image_text_catalog_hybrid" if use_text else "image_only",
        })
        ranked.append(result)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    relevant = _filter_visual_results(ranked, infer_product_type)
    return relevant[:top_k]


def get_more_like_this(product_id, top_k=6):
    current_product = get_product_by_id(product_id)
    if not current_product or not current_product.get("embedding"):
        return []

    products = get_similar_candidate_products(
        category=current_product["category"],
        article_type=current_product["articleType"],
        gender=current_product.get("gender"),
    )

    similarities = []
    for product in products:
        if product["_id"] == current_product["_id"] or not product.get("embedding"):
            continue

        clip_score = cosine_similarity(current_product["embedding"], product["embedding"])
        final_score = clip_score * 0.80
        reasons = ["Similar visual appearance"]

        for field, bonus, reason in (
            ("color", 0.05, "Same color"),
            ("season", 0.03, "Suitable for the same season"),
            ("usage", 0.02, "Designed for the same usage"),
        ):
            if current_product.get(field) and product.get(field) and str(current_product[field]).lower() == str(product[field]).lower():
                final_score += bonus
                reasons.append(reason)

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
            "reason": ", ".join(reasons),
        })

    similarities.sort(key=lambda item: item["score"], reverse=True)
    return similarities[:top_k]


def find_similar_shopify_products(query_embedding, top_k=5):
    return find_hybrid_shopify_products(
        image_embedding=query_embedding,
        products=get_all_shopify_products(),
        text_embedding=None,
        top_k=top_k,
        infer_product_type=True,
    )


def find_more_like_shopify_product(
    reference_product: dict[str, Any],
    products: list[dict[str, Any]],
    top_k: int = 5,
    cheaper_only: bool = False,
) -> list[dict[str, Any]]:
    """
    Rank catalog products against a product selected from conversation
    memory.

    Product names are never hardcoded. The reference comes from the
    customer's previously displayed results.
    """
    reference_image = (
        reference_product.get(
            "image_embedding"
        )
        or reference_product.get(
            "embedding"
        )
    )
    reference_text = (
        reference_product.get(
            "text_embedding"
        )
    )
    reference_type = (
        _normalise(
            reference_product.get(
                "product_type"
            )
        )
    )

    try:
        reference_price = float(
            reference_product.get(
                "price"
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        reference_price = None

    reference_identity = (
        str(
            reference_product.get(
                "shopify_id"
            )
            or reference_product.get(
                "id"
            )
            or reference_product.get(
                "handle"
            )
            or ""
        )
    )

    ranked: list[
        dict[str, Any]
    ] = []

    for product in products or []:
        product_identity = str(
            product.get(
                "shopify_id"
            )
            or product.get(
                "id"
            )
            or product.get(
                "handle"
            )
            or ""
        )

        if (
            reference_identity
            and product_identity
            == reference_identity
        ):
            continue

        product_type = _normalise(
            product.get(
                "product_type"
            )
        )

        if (
            reference_type
            and product_type
            and product_type
            != reference_type
        ):
            continue

        try:
            product_price = float(
                product.get(
                    "price"
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            product_price = None

        if (
            cheaper_only
            and reference_price
            is not None
            and (
                product_price
                is None
                or product_price
                >= reference_price
            )
        ):
            continue

        product_image = (
            product.get(
                "image_embedding"
            )
            or product.get(
                "embedding"
            )
        )
        product_text = (
            product.get(
                "text_embedding"
            )
        )

        image_score = (
            max(
                0.0,
                cosine_similarity(
                    reference_image,
                    product_image,
                ),
            )
            if (
                reference_image
                and product_image
            )
            else 0.0
        )

        text_score = (
            max(
                0.0,
                cosine_similarity(
                    reference_text,
                    product_text,
                ),
            )
            if (
                reference_text
                and product_text
            )
            else 0.0
        )

        available_scores = []

        if (
            reference_image
            and product_image
        ):
            available_scores.append(
                (
                    0.60,
                    image_score,
                )
            )

        if (
            reference_text
            and product_text
        ):
            available_scores.append(
                (
                    0.40,
                    text_score,
                )
            )

        if not available_scores:
            continue

        total_weight = sum(
            weight
            for weight, _
            in available_scores
        )

        final_score = sum(
            weight * score
            for weight, score
            in available_scores
        ) / total_weight

        result = (
            _shopify_product_result(
                product
            )
        )

        result.update({
            "score": round(
                final_score,
                4,
            ),
            "imageScore": round(
                image_score,
                4,
            )
            if reference_image
            and product_image
            else None,
            "textScore": round(
                text_score,
                4,
            )
            if reference_text
            and product_text
            else None,
            "rankingMode": (
                "conversation_more_like_this"
            ),
            "referenceProductId": (
                reference_product.get(
                    "id"
                )
            ),
            "referenceProductTitle": (
                reference_product.get(
                    "title"
                )
            ),
        })

        ranked.append(
            result
        )

    ranked.sort(
        key=lambda item: (
            item.get("score")
            or 0.0
        ),
        reverse=True,
    )

    return ranked[
        :max(
            1,
            min(
                int(top_k),
                20,
            ),
        )
    ]

