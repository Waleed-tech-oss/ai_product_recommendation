import re
from difflib import SequenceMatcher
from typing import Any


def _clean(value: str) -> str:
    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            (value or "").lower(),
        )
    )


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(_clean(left).split())
    right_tokens = set(_clean(right).split())

    if not left_tokens or not right_tokens:
        return 0.0

    return (
        len(left_tokens.intersection(right_tokens))
        / len(left_tokens.union(right_tokens))
    )


def _match_score(target: str, title: str) -> float:
    clean_target = _clean(target)
    clean_title = _clean(title)

    if not clean_target or not clean_title:
        return 0.0

    if clean_target == clean_title:
        return 1.0

    sequence_score = SequenceMatcher(
        None,
        clean_target,
        clean_title,
    ).ratio()

    overlap_score = _token_overlap(
        clean_target,
        clean_title,
    )

    substring_bonus = (
        0.15
        if clean_target in clean_title
        else 0.0
    )

    return min(
        1.0,
        (
            sequence_score * 0.65
            + overlap_score * 0.35
            + substring_bonus
        ),
    )


def extract_comparison_targets(query: str) -> list[str]:
    """
    Fallback when Groq does not return comparisonTargets.

    Handles:
    - Compare Alpha vs Beta
    - Alpha and Beta compare
    - Alpha aur Beta compare kro
    """
    text = query or ""

    text = re.sub(
        r"\b(compare|comparison|compare kro|compare karo|"
        r"farq batao|muqabla)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b(kro|karo|kar do|batao|please)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    parts = re.split(
        r"\s+(?:vs\.?|versus|and|aur)\s+|,",
        text,
        flags=re.IGNORECASE,
    )

    return [
        " ".join(part.split()).strip(" .?!")
        for part in parts
        if len(" ".join(part.split()).strip(" .?!")) >= 2
    ][:4]


def _suggest_titles(
    target: str,
    products: list[dict[str, Any]],
    limit: int = 3,
) -> list[str]:
    ranked = sorted(
        (
            (
                _match_score(
                    target,
                    str(product.get("title", "")),
                ),
                str(product.get("title", "")),
            )
            for product in products
            if product.get("title")
        ),
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        title
        for score, title in ranked[:limit]
        if score >= 0.25
    ]


def match_comparison_products(
    targets: list[str],
    products: list[dict[str, Any]],
) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    used_ids: set[Any] = set()

    for target in targets[:4]:
        best_product = None
        best_score = 0.0

        for product in products:
            product_id = product.get("id")

            if product_id in used_ids:
                continue

            score = _match_score(
                target,
                str(product.get("title", "")),
            )

            if score > best_score:
                best_product = product
                best_score = score

        if best_product and best_score >= 0.45:
            used_ids.add(best_product.get("id"))
            matched.append({
                **best_product,
                "comparisonMatchScore": round(
                    best_score,
                    4,
                ),
                "comparisonTarget": target,
            })
        else:
            unmatched.append({
                "target": target,
                "suggestions": _suggest_titles(
                    target,
                    products,
                ),
            })

    return {
        "matched": matched,
        "unmatched": unmatched,
    }


def public_product(
    product: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in product.items()
        if key != "embedding"
    }


def build_product_comparison(
    products: list[dict[str, Any]],
) -> dict[str, Any]:
    public_products = [
        public_product(product)
        for product in products[:4]
    ]

    prices = [
        (
            product.get("id"),
            float(product["price"]),
            product.get("title"),
        )
        for product in public_products
        if product.get("price") is not None
    ]

    price_summary: dict[str, Any] = {
        "cheapestProductId": None,
        "mostExpensiveProductId": None,
        "priceDifference": None,
    }

    if prices:
        cheapest = min(
            prices,
            key=lambda item: item[1],
        )
        most_expensive = max(
            prices,
            key=lambda item: item[1],
        )

        price_summary = {
            "cheapestProductId": cheapest[0],
            "cheapestProductTitle": cheapest[2],
            "mostExpensiveProductId": (
                most_expensive[0]
            ),
            "mostExpensiveProductTitle": (
                most_expensive[2]
            ),
            "priceDifference": round(
                most_expensive[1] - cheapest[1],
                2,
            ),
        }

    rows = [
        {
            "field": "price",
            "label": "Price",
            "values": [
                {
                    "productId": product.get("id"),
                    "value": product.get("price"),
                }
                for product in public_products
            ],
        },
        {
            "field": "vendor",
            "label": "Vendor",
            "values": [
                {
                    "productId": product.get("id"),
                    "value": product.get("vendor"),
                }
                for product in public_products
            ],
        },
        {
            "field": "product_type",
            "label": "Product Type",
            "values": [
                {
                    "productId": product.get("id"),
                    "value": product.get(
                        "product_type"
                    ),
                }
                for product in public_products
            ],
        },
        {
            "field": "sku",
            "label": "SKU",
            "values": [
                {
                    "productId": product.get("id"),
                    "value": product.get("sku"),
                }
                for product in public_products
            ],
        },
    ]

    return {
        "products": public_products,
        "rows": rows,
        "priceSummary": price_summary,
        "comparedFields": [
            "price",
            "vendor",
            "product_type",
            "sku",
        ],
        "missingFields": [
            "ratings",
            "reviews",
            "availability",
            "inventory",
            "material",
        ],
    }
