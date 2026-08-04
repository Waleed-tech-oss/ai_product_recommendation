from __future__ import annotations

import os
from typing import Any

import numpy as np

from database.postgres import (
    get_all_shopify_products,
    get_product_by_id,
    get_similar_candidate_products,
)


def cosine_similarity(
    vec1,
    vec2,
) -> float:
    """
    Safely calculate cosine similarity for two embeddings.
    """
    left = np.asarray(
        vec1,
        dtype=np.float32,
    )
    right = np.asarray(
        vec2,
        dtype=np.float32,
    )

    if (
        left.ndim != 1
        or right.ndim != 1
        or left.shape != right.shape
    ):
        return 0.0

    denominator = (
        np.linalg.norm(left)
        * np.linalg.norm(right)
    )

    if denominator <= 1e-12:
        return 0.0

    return float(
        np.dot(left, right)
        / denominator
    )


def _shopify_product_result(
    product: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": str(product["id"]),
        "shopify_id": product.get(
            "shopify_id"
        ),
        "title": product.get("title"),
        "handle": product.get("handle"),
        "vendor": product.get("vendor"),
        "product_type": product.get(
            "product_type"
        ),
        "image_url": product.get(
            "image_url"
        ),
        "sku": product.get("sku"),
        "price": product.get("price"),
    }



def _normalized_product_type(value):
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .split()
    )


def _read_float_setting(
    name,
    default,
    minimum=0.0,
    maximum=1.0,
):
    try:
        value = float(
            os.getenv(
                name,
                str(default),
            )
        )
    except ValueError:
        value = default

    return max(
        minimum,
        min(value, maximum),
    )


def _filter_visual_results(
    ranked_products,
    infer_product_type,
):
    """
    Keep visually relevant products and avoid mixing unrelated
    catalog categories into an uploaded-image result.

    When no exact product type was supplied by the customer,
    the highest-scoring product is used to infer the likely
    category. Example: top result is a snowboard, so shirts
    are excluded from the returned list.
    """
    if not ranked_products:
        return []

    top_result = ranked_products[0]
    top_score = float(
        top_result.get("score")
        or 0.0
    )

    minimum_score = _read_float_setting(
        "MIN_VISUAL_RESULT_SCORE",
        0.20,
    )
    maximum_score_gap = _read_float_setting(
        "MAX_VISUAL_SCORE_GAP",
        0.12,
    )

    cutoff = max(
        minimum_score,
        top_score - maximum_score_gap,
    )

    filtered = [
        product
        for product in ranked_products
        if float(
            product.get("score")
            or 0.0
        ) >= cutoff
    ]

    if not filtered:
        filtered = [top_result]

    if not infer_product_type:
        return filtered

    inferred_type = _normalized_product_type(
        top_result.get("product_type")
    )

    if not inferred_type:
        return filtered

    same_type = [
        product
        for product in filtered
        if _normalized_product_type(
            product.get("product_type")
        ) == inferred_type
    ]

    if not same_type:
        return filtered

    for product in same_type:
        product["inferredProductType"] = (
            top_result.get("product_type")
        )

    return same_type


# ----------------------------------------
# Text-to-product semantic ranking
# ----------------------------------------

def find_similar_products(
    query_embedding,
    products,
    top_k=5,
):
    similarities = []

    for product in products:
        embedding = product.get(
            "embedding"
        )

        if not embedding:
            continue

        score = cosine_similarity(
            query_embedding,
            embedding,
        )

        result = _shopify_product_result(
            product
        )
        result["score"] = round(
            max(0.0, score),
            4,
        )

        similarities.append(result)

    similarities.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return similarities[:top_k]


# ----------------------------------------
# Image + text hybrid Shopify ranking
# ----------------------------------------

def find_hybrid_shopify_products(
    image_embedding,
    products,
    text_embedding=None,
    top_k=5,
    image_weight=None,
    infer_product_type=True,
):
    """
    Rank filtered Shopify products using their stored image
    embeddings.

    Image-only:
        final score = image cosine similarity

    Image + text:
        final score =
            image_score * image_weight
            + text_score * text_weight

    Because CLIP uses a shared text/image vector space, the text
    embedding can be compared directly with the stored product-image
    embeddings.
    """
    if image_weight is None:
        try:
            image_weight = float(
                os.getenv(
                    "HYBRID_IMAGE_WEIGHT",
                    "0.70",
                )
            )
        except ValueError:
            image_weight = 0.70

    image_weight = max(
        0.0,
        min(image_weight, 1.0),
    )
    text_weight = 1.0 - image_weight

    use_text = text_embedding is not None
    similarities = []

    for product in products:
        product_embedding = product.get(
            "embedding"
        )

        if not product_embedding:
            continue

        raw_image_score = cosine_similarity(
            image_embedding,
            product_embedding,
        )
        image_score = max(
            0.0,
            raw_image_score,
        )

        if use_text:
            raw_text_score = cosine_similarity(
                text_embedding,
                product_embedding,
            )
            text_score = max(
                0.0,
                raw_text_score,
            )

            final_score = (
                image_score * image_weight
                + text_score * text_weight
            )
        else:
            text_score = None
            final_score = image_score

        result = _shopify_product_result(
            product
        )

        result.update({
            "imageScore": round(
                image_score,
                4,
            ),
            "textScore": (
                round(text_score, 4)
                if text_score is not None
                else None
            ),
            "score": round(
                max(0.0, final_score),
                4,
            ),
            "rankingMode": (
                "image_text_hybrid"
                if use_text
                else "image_only"
            ),
        })

        similarities.append(result)

    similarities.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    relevant_results = _filter_visual_results(
        ranked_products=similarities,
        infer_product_type=infer_product_type,
    )

    return relevant_results[:top_k]


# ----------------------------------------
# More Like This
# ----------------------------------------

def get_more_like_this(
    product_id,
    top_k=6,
):
    current_product = get_product_by_id(
        product_id
    )

    if not current_product:
        return []

    current_embedding = (
        current_product.get("embedding")
    )

    if not current_embedding:
        return []

    products = (
        get_similar_candidate_products(
            category=current_product[
                "category"
            ],
            article_type=current_product[
                "articleType"
            ],
            gender=current_product.get(
                "gender"
            ),
        )
    )

    similarities = []

    for product in products:
        if (
            product["_id"]
            == current_product["_id"]
        ):
            continue

        embedding = product.get(
            "embedding"
        )

        if not embedding:
            continue

        clip_score = cosine_similarity(
            current_embedding,
            embedding,
        )

        final_score = clip_score * 0.80
        reasons = [
            "Similar visual appearance"
        ]

        if (
            current_product.get("color")
            and product.get("color")
            and current_product[
                "color"
            ].lower()
            == product["color"].lower()
        ):
            final_score += 0.05
            reasons.append("Same color")

        if (
            current_product.get("season")
            and product.get("season")
            and current_product[
                "season"
            ].lower()
            == product[
                "season"
            ].lower()
        ):
            final_score += 0.03
            reasons.append(
                "Suitable for the same season"
            )

        if (
            current_product.get("usage")
            and product.get("usage")
            and current_product[
                "usage"
            ].lower()
            == product["usage"].lower()
        ):
            final_score += 0.02
            reasons.append(
                "Designed for the same usage"
            )

        similarities.append({
            "id": str(product["_id"]),
            "name": product.get("name"),
            "description": product.get(
                "description"
            ),
            "category": product.get(
                "category"
            ),
            "subCategory": product.get(
                "subCategory"
            ),
            "articleType": product.get(
                "articleType"
            ),
            "gender": product.get(
                "gender"
            ),
            "color": product.get("color"),
            "season": product.get(
                "season"
            ),
            "usage": product.get("usage"),
            "image": product.get("image"),
            "price": product.get("price"),
            "clipScore": round(
                float(clip_score),
                4,
            ),
            "score": round(
                float(final_score),
                4,
            ),
            "isMoreLikeThis": True,
            "reason": ", ".join(
                reasons
            ),
        })

    similarities.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return similarities[:top_k]


# ----------------------------------------
# Existing Shopify image recommendation
# ----------------------------------------

def find_similar_shopify_products(
    query_embedding,
    top_k=5,
):
    products = (
        get_all_shopify_products()
    )

    return find_hybrid_shopify_products(
        image_embedding=query_embedding,
        products=products,
        text_embedding=None,
        top_k=top_k,
        infer_product_type=True,
    )
