import os
from typing import Any, Callable


SearchFunction = Callable[
    [dict[str, Any], int],
    list[dict[str, Any]],
]


def public_product(
    product: dict[str, Any],
) -> dict[str, Any]:
    """
    Remove the product embedding before sending product data
    to the frontend.
    """
    return {
        key: value
        for key, value in product.items()
        if key != "embedding"
    }


def localized(
    language: str,
    english: str,
    roman_urdu: str,
) -> str:
    """
    Return a message in the detected response language.
    """
    return (
        roman_urdu
        if language == "roman_urdu"
        else english
    )


def build_multiple_type_clarification(
    product_types: list[str],
    response_language: str,
) -> dict[str, Any]:
    """
    Ask the user to choose one product type when the query
    contains multiple catalog product types.

    Example:
        shirt with snowboard
    """
    readable = ", ".join(product_types)

    message = localized(
        response_language,
        (
            "I found more than one product type in your request "
            f"({readable}). Which one should I search for?"
        ),
        (
            "Aapki query mein aik se zyada product types mile hain "
            f"({readable}). Aap kis product ko search karna chahte hain?"
        ),
    )

    return {
        "intent": "clarification",
        "clarificationType": "multiple_product_types",
        "message": message,
        "options": [
            {
                "type": "select_product_type",
                "label": localized(
                    response_language,
                    f"Search {product_type}",
                    f"{product_type} search karo",
                ),
                "message": localized(
                    response_language,
                    f"Show me {product_type}",
                    f"Mujhy {product_type} dikhao",
                ),
                "filters": {
                    "productType": product_type,
                },
            }
            for product_type in product_types[:4]
        ],
        "recommendedProducts": [],
    }


def _candidate_key(
    filters: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    """
    Create a stable key so duplicate relaxation options
    are not returned.
    """
    return tuple(
        sorted(
            (
                str(key),
                repr(value),
            )
            for key, value in filters.items()
        )
    )


def _add_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[tuple[str, str], ...]],
    candidate_type: str,
    filters: dict[str, Any],
    label: str,
    message: str,
) -> None:
    """
    Add a relaxation option only when its filters are unique.
    """
    key = _candidate_key(filters)

    if key in seen:
        return

    seen.add(key)

    candidates.append({
        "type": candidate_type,
        "filters": filters,
        "label": label,
        "message": message,
    })


def _relaxation_candidates(
    filters: dict[str, Any],
    response_language: str,
) -> list[dict[str, Any]]:
    """
    Build progressively broader search options.

    Single-filter relaxations are attempted first.
    Combined relaxations are then attempted for cases where
    removing only one filter still produces zero products.

    Example:
        Burton snowboard under 10

    Possible combined relaxation:
        remove vendor + maxPrice
        keep productType = snowboard
    """
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()

    vendor = filters.get("vendor")
    product_type = filters.get("productType")
    max_price = filters.get("maxPrice")
    min_price = filters.get("minPrice")

    # --------------------------------------------------
    # Single-filter relaxations
    # --------------------------------------------------

    if vendor:
        relaxed = dict(filters)
        relaxed.pop("vendor", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_vendor",
            filters=relaxed,
            label=localized(
                response_language,
                f"Try all vendors instead of {vendor}",
                f"{vendor} ke bajaye sab vendors dekhein",
            ),
            message=localized(
                response_language,
                (
                    f"Show matching products from all vendors "
                    f"instead of only {vendor}"
                ),
                (
                    f"Sirf {vendor} ke bajaye sab vendors ke "
                    "matching products dikhao"
                ),
            ),
        )

    if max_price is not None:
        relaxed = dict(filters)
        relaxed.pop("maxPrice", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_max_price",
            filters=relaxed,
            label=localized(
                response_language,
                f"Show options above ${max_price} too",
                f"${max_price} se zyada price wale options bhi dekhein",
            ),
            message=localized(
                response_language,
                (
                    f"Show matching products without the "
                    f"${max_price} maximum-price limit"
                ),
                (
                    f"${max_price} maximum-price limit ke baghair "
                    "matching products dikhao"
                ),
            ),
        )

    if min_price is not None:
        relaxed = dict(filters)
        relaxed.pop("minPrice", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_min_price",
            filters=relaxed,
            label=localized(
                response_language,
                f"Show options below ${min_price} too",
                f"${min_price} se kam price wale options bhi dekhein",
            ),
            message=localized(
                response_language,
                (
                    f"Show matching products without the "
                    f"${min_price} minimum-price limit"
                ),
                (
                    f"${min_price} minimum-price limit ke baghair "
                    "matching products dikhao"
                ),
            ),
        )

    if product_type:
        relaxed = dict(filters)
        relaxed.pop("productType", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_product_type",
            filters=relaxed,
            label=localized(
                response_language,
                f"Search related products instead of only {product_type}",
                f"Sirf {product_type} ke bajaye related products dekhein",
            ),
            message=localized(
                response_language,
                (
                    f"Show related products instead of only "
                    f"{product_type}"
                ),
                (
                    f"Sirf {product_type} ke bajaye related "
                    "products dikhao"
                ),
            ),
        )

    # --------------------------------------------------
    # Combined relaxations
    # --------------------------------------------------

    if vendor and max_price is not None:
        relaxed = dict(filters)
        relaxed.pop("vendor", None)
        relaxed.pop("maxPrice", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_vendor_and_max_price",
            filters=relaxed,
            label=localized(
                response_language,
                (
                    f"Show matching products without {vendor} "
                    f"and the ${max_price} limit"
                ),
                (
                    f"{vendor} aur ${max_price} limit ke baghair "
                    "matching products dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    f"Show matching products from all vendors "
                    f"without the ${max_price} price limit"
                ),
                (
                    f"Sab vendors ke matching products "
                    f"${max_price} price limit ke baghair dikhao"
                ),
            ),
        )

    if vendor and min_price is not None:
        relaxed = dict(filters)
        relaxed.pop("vendor", None)
        relaxed.pop("minPrice", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_vendor_and_min_price",
            filters=relaxed,
            label=localized(
                response_language,
                (
                    f"Show matching products without {vendor} "
                    f"and the ${min_price} minimum"
                ),
                (
                    f"{vendor} aur ${min_price} minimum ke baghair "
                    "matching products dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products from all vendors "
                    f"without the ${min_price} minimum-price limit"
                ),
                (
                    "Sab vendors ke matching products "
                    f"${min_price} minimum-price limit ke baghair dikhao"
                ),
            ),
        )

    if product_type and max_price is not None:
        relaxed = dict(filters)
        relaxed.pop("productType", None)
        relaxed.pop("maxPrice", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_product_type_and_max_price",
            filters=relaxed,
            label=localized(
                response_language,
                (
                    f"Show related products without the "
                    f"${max_price} limit"
                ),
                (
                    f"${max_price} limit ke baghair related "
                    "products dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show related products without the "
                    f"${max_price} maximum-price limit"
                ),
                (
                    "Related products "
                    f"${max_price} maximum-price limit ke baghair dikhao"
                ),
            ),
        )

    if product_type and min_price is not None:
        relaxed = dict(filters)
        relaxed.pop("productType", None)
        relaxed.pop("minPrice", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_product_type_and_min_price",
            filters=relaxed,
            label=localized(
                response_language,
                (
                    f"Show related products without the "
                    f"${min_price} minimum"
                ),
                (
                    f"${min_price} minimum ke baghair related "
                    "products dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show related products without the "
                    f"${min_price} minimum-price limit"
                ),
                (
                    "Related products "
                    f"${min_price} minimum-price limit ke baghair dikhao"
                ),
            ),
        )

    if vendor and product_type:
        relaxed = dict(filters)
        relaxed.pop("vendor", None)
        relaxed.pop("productType", None)

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="remove_vendor_and_product_type",
            filters=relaxed,
            label=localized(
                response_language,
                "Search the wider catalog",
                "Zyada broad catalog search karein",
            ),
            message=localized(
                response_language,
                "Show matching products from the wider catalog",
                "Wider catalog se matching products dikhao",
            ),
        )

    # Final fallback: remove all restrictive search filters but preserve sort.
    restrictive_keys = {
        "vendor",
        "productType",
        "minPrice",
        "maxPrice",
    }

    if any(
        key in filters
        for key in restrictive_keys
    ):
        relaxed = {
            key: value
            for key, value in filters.items()
            if key not in restrictive_keys
        }

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type="broaden_all_filters",
            filters=relaxed,
            label=localized(
                response_language,
                "Browse available products",
                "Available products dekhein",
            ),
            message=localized(
                response_language,
                "Show me available products",
                "Mujhy available products dikhao",
            ),
        )

    return candidates


def _safe_search(
    search_function: SearchFunction,
    filters: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    """
    Prevent a failed relaxation query from crashing the
    complete chat request.
    """
    try:
        products = search_function(
            filters,
            limit,
        )

        if isinstance(products, list):
            return products

    except Exception as error:
        print(
            "\n========== CLARIFICATION SEARCH ERROR =========="
        )
        print(error)
        print(
            "================================================\n"
        )

    return []


def build_no_result_clarification(
    filters: dict[str, Any],
    response_language: str,
    search_function: SearchFunction,
) -> dict[str, Any]:
    """
    Return useful broader-search options instead of returning
    an unrelated product.

    Only options that actually produce products are returned.
    """
    options: list[dict[str, Any]] = []

    for candidate in _relaxation_candidates(
        filters,
        response_language,
    ):
        products = _safe_search(
            search_function=search_function,
            filters=candidate["filters"],
            limit=3,
        )

        if not products:
            continue

        options.append({
            **candidate,
            "previewProducts": [
                public_product(product)
                for product in products[:3]
            ],
        })

        if len(options) >= 3:
            break

    if options:
        message = localized(
            response_language,
            (
                "No exact product matched all your filters. "
                "Choose one option to broaden the search."
            ),
            (
                "Aapke tamam filters ke saath exact product nahi mila. "
                "Search ko broad karne ke liye aik option select karein."
            ),
        )
    else:
        message = localized(
            response_language,
            (
                "I could not find a relevant product. "
                "Try another product type, vendor, or budget."
            ),
            (
                "Mujhy relevant product nahi mila. "
                "Product type, vendor ya budget change karke dekhein."
            ),
        )

    return {
        "intent": "clarification",
        "clarificationType": "no_exact_match",
        "message": message,
        "options": options,
        "recommendedProducts": [],
    }


def semantic_result_is_low_confidence(
    recommendations: list[dict[str, Any]],
) -> bool:
    """
    Reject weak semantic results only when a numeric score exists.

    Configure in .env:

        MIN_SEMANTIC_SCORE=0.20

    Suggested testing range:

        0.15 = lenient
        0.20 = balanced
        0.25 = strict
    """
    if not recommendations:
        return True

    top_score = recommendations[0].get(
        "score"
    )

    if not isinstance(
        top_score,
        (int, float),
    ):
        # If no numeric similarity score exists, do not reject
        # the result automatically.
        return False

    try:
        threshold = float(
            os.getenv(
                "MIN_SEMANTIC_SCORE",
                "0.20",
            )
        )
    except ValueError:
        threshold = 0.20

    # Keep the threshold within a valid similarity range.
    threshold = max(
        0.0,
        min(threshold, 1.0),
    )

    return float(top_score) < threshold


def build_low_confidence_clarification(
    filters: dict[str, Any],
    response_language: str,
    search_function: SearchFunction,
) -> dict[str, Any]:
    """
    Convert weak semantic matches into a clarification response.
    """
    response = build_no_result_clarification(
        filters=filters,
        response_language=response_language,
        search_function=search_function,
    )

    response["clarificationType"] = (
        "low_semantic_confidence"
    )

    response["message"] = localized(
        response_language,
        (
            "I found products, but their match confidence is too low. "
            "Please clarify your request or broaden one filter."
        ),
        (
            "Products mile hain, lekin unka match confidence bohat kam hai. "
            "Apni request clear karein ya koi filter broad karein."
        ),
    )

    return response