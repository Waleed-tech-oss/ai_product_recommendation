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
    Remove embeddings before returning product data
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
    return (
        roman_urdu
        if language == "roman_urdu"
        else english
    )


def _join_product_types(
    product_types: list[str],
    response_language: str,
) -> str:
    clean_types = [
        str(product_type).strip()
        for product_type in product_types
        if str(product_type).strip()
    ]

    if not clean_types:
        return ""

    if len(clean_types) == 1:
        return clean_types[0]

    connector = (
        " aur "
        if response_language == "roman_urdu"
        else " and "
    )

    if len(clean_types) == 2:
        return connector.join(
            clean_types
        )

    return (
        ", ".join(clean_types[:-1])
        + connector
        + clean_types[-1]
    )


def build_multiple_type_clarification(
    product_types: list[str],
    response_language: str,
) -> dict[str, Any]:
    """
    Ask the customer what they intended when a request contains
    multiple product types but is not clearly a category list.

    Example:
        shirt with snowboard

    Options:
        Search shirt
        Search snowboard
        Show both shirt and snowboard
    """
    clean_types: list[str] = []
    seen: set[str] = set()

    for product_type in product_types:
        clean_type = " ".join(
            str(product_type or "")
            .strip()
            .split()
        )

        key = clean_type.lower()

        if (
            not clean_type
            or key in seen
        ):
            continue

        seen.add(key)
        clean_types.append(
            clean_type
        )

        if len(clean_types) >= 4:
            break

    readable = ", ".join(
        clean_types
    )

    message = localized(
        response_language,
        (
            "I found more than one product type in your request "
            f"({readable}). What would you like me to search?"
        ),
        (
            "Aapki query mein aik se zyada product types mile hain "
            f"({readable}). Aap kya search karna chahte hain?"
        ),
    )

    options = [
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
        for product_type in clean_types
    ]

    # Combined option: the generated message is intentionally written
    # as an explicit list using "and/aur", so the multi-category parser
    # handles it directly instead of asking the same clarification again.
    if len(clean_types) >= 2:
        combined_types = (
            _join_product_types(
                clean_types,
                response_language,
            )
        )

        options.append({
            "type": "search_all_product_types",
            "label": localized(
                response_language,
                (
                    f"Show all: "
                    f"{combined_types}"
                ),
                (
                    f"Sab dikhao: "
                    f"{combined_types}"
                ),
            ),
            "message": localized(
                response_language,
                (
                    f"Show me "
                    f"{combined_types}"
                ),
                (
                    f"Mujhy "
                    f"{combined_types} "
                    "dono dikhao"
                    if len(clean_types) == 2
                    else (
                        f"Mujhy "
                        f"{combined_types} "
                        "sab dikhao"
                    )
                ),
            ),
            "productTypes": clean_types,
        })

    return {
        "intent": "clarification",
        "clarificationType": (
            "multiple_product_types"
        ),
        "message": message,
        "options": options,
        "recommendedProducts": [],
    }


def _candidate_key(
    filters: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                str(key),
                repr(value),
            )
            for key, value
            in filters.items()
        )
    )


def _add_candidate(
    candidates: list[dict[str, Any]],
    seen: set[
        tuple[
            tuple[str, str],
            ...
        ]
    ],
    candidate_type: str,
    filters: dict[str, Any],
    label: str,
    message: str,
) -> None:
    key = _candidate_key(
        filters
    )

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
    candidates: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[
            tuple[str, str],
            ...
        ]
    ] = set()

    vendor = filters.get(
        "vendor"
    )
    product_type = filters.get(
        "productType"
    )
    max_price = filters.get(
        "maxPrice"
    )
    min_price = filters.get(
        "minPrice"
    )

    if vendor:
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "vendor",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_vendor"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Try all vendors "
                    f"instead of {vendor}"
                ),
                (
                    f"{vendor} ke bajaye "
                    "sab vendors dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products "
                    "from all vendors instead "
                    f"of only {vendor}"
                ),
                (
                    f"Sirf {vendor} ke bajaye "
                    "sab vendors ke matching "
                    "products dikhao"
                ),
            ),
        )

    if max_price is not None:
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "maxPrice",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_max_price"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Show options above "
                    f"${max_price} too"
                ),
                (
                    f"${max_price} se zyada "
                    "price wale options bhi "
                    "dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products "
                    "without the "
                    f"${max_price} maximum-"
                    "price limit"
                ),
                (
                    f"${max_price} maximum-"
                    "price limit ke baghair "
                    "matching products dikhao"
                ),
            ),
        )

    if min_price is not None:
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "minPrice",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_min_price"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Show options below "
                    f"${min_price} too"
                ),
                (
                    f"${min_price} se kam "
                    "price wale options bhi "
                    "dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products "
                    "without the "
                    f"${min_price} minimum-"
                    "price limit"
                ),
                (
                    f"${min_price} minimum-"
                    "price limit ke baghair "
                    "matching products dikhao"
                ),
            ),
        )

    if product_type:
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "productType",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_product_type"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Search related products "
                    "instead of only "
                    f"{product_type}"
                ),
                (
                    f"Sirf {product_type} "
                    "ke bajaye related "
                    "products dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show related products "
                    "instead of only "
                    f"{product_type}"
                ),
                (
                    f"Sirf {product_type} "
                    "ke bajaye related "
                    "products dikhao"
                ),
            ),
        )

    if (
        vendor
        and max_price
        is not None
    ):
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "vendor",
            None,
        )
        relaxed.pop(
            "maxPrice",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_vendor_and_max_price"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Show matching products "
                    f"without {vendor} and the "
                    f"${max_price} limit"
                ),
                (
                    f"{vendor} aur "
                    f"${max_price} limit ke "
                    "baghair matching products "
                    "dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products "
                    "from all vendors without "
                    f"the ${max_price} price limit"
                ),
                (
                    "Sab vendors ke matching "
                    f"products ${max_price} price "
                    "limit ke baghair dikhao"
                ),
            ),
        )

    if (
        vendor
        and min_price
        is not None
    ):
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "vendor",
            None,
        )
        relaxed.pop(
            "minPrice",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_vendor_and_min_price"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Show matching products "
                    f"without {vendor} and the "
                    f"${min_price} minimum"
                ),
                (
                    f"{vendor} aur "
                    f"${min_price} minimum ke "
                    "baghair matching products "
                    "dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products "
                    "from all vendors without "
                    f"the ${min_price} minimum-"
                    "price limit"
                ),
                (
                    "Sab vendors ke matching "
                    f"products ${min_price} "
                    "minimum-price limit ke "
                    "baghair dikhao"
                ),
            ),
        )

    if (
        product_type
        and max_price
        is not None
    ):
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "productType",
            None,
        )
        relaxed.pop(
            "maxPrice",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_product_type_and_max_price"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Show related products "
                    f"without the ${max_price} "
                    "limit"
                ),
                (
                    f"${max_price} limit ke "
                    "baghair related products "
                    "dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show related products "
                    "without the "
                    f"${max_price} maximum-"
                    "price limit"
                ),
                (
                    "Related products "
                    f"${max_price} maximum-"
                    "price limit ke baghair "
                    "dikhao"
                ),
            ),
        )

    if (
        product_type
        and min_price
        is not None
    ):
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "productType",
            None,
        )
        relaxed.pop(
            "minPrice",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_product_type_and_min_price"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                (
                    "Show related products "
                    f"without the ${min_price} "
                    "minimum"
                ),
                (
                    f"${min_price} minimum ke "
                    "baghair related products "
                    "dekhein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show related products "
                    "without the "
                    f"${min_price} minimum-"
                    "price limit"
                ),
                (
                    "Related products "
                    f"${min_price} minimum-"
                    "price limit ke baghair "
                    "dikhao"
                ),
            ),
        )

    if (
        vendor
        and product_type
    ):
        relaxed = dict(
            filters
        )
        relaxed.pop(
            "vendor",
            None,
        )
        relaxed.pop(
            "productType",
            None,
        )

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "remove_vendor_and_product_type"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                "Search the wider catalog",
                (
                    "Zyada broad catalog "
                    "search karein"
                ),
            ),
            message=localized(
                response_language,
                (
                    "Show matching products "
                    "from the wider catalog"
                ),
                (
                    "Wider catalog se matching "
                    "products dikhao"
                ),
            ),
        )

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
            for key, value
            in filters.items()
            if key
            not in restrictive_keys
        }

        _add_candidate(
            candidates=candidates,
            seen=seen,
            candidate_type=(
                "broaden_all_filters"
            ),
            filters=relaxed,
            label=localized(
                response_language,
                "Browse available products",
                "Available products dekhein",
            ),
            message=localized(
                response_language,
                "Show me available products",
                (
                    "Mujhy available products "
                    "dikhao"
                ),
            ),
        )

    return candidates


def _safe_search(
    search_function: SearchFunction,
    filters: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    try:
        products = search_function(
            filters,
            limit,
        )

        if isinstance(
            products,
            list,
        ):
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
    options: list[
        dict[str, Any]
    ] = []

    for candidate in (
        _relaxation_candidates(
            filters,
            response_language,
        )
    ):
        products = _safe_search(
            search_function=(
                search_function
            ),
            filters=(
                candidate["filters"]
            ),
            limit=3,
        )

        if not products:
            continue

        options.append({
            **candidate,
            "previewProducts": [
                public_product(
                    product
                )
                for product
                in products[:3]
            ],
        })

        if len(options) >= 3:
            break

    if options:
        message = localized(
            response_language,
            (
                "No exact product matched "
                "all your filters. Choose "
                "one option to broaden the "
                "search."
            ),
            (
                "Aapke tamam filters ke "
                "saath exact product nahi "
                "mila. Search ko broad karne "
                "ke liye aik option select "
                "karein."
            ),
        )
    else:
        message = localized(
            response_language,
            (
                "I could not find a relevant "
                "product. Try another product "
                "type, vendor, or budget."
            ),
            (
                "Mujhy relevant product nahi "
                "mila. Product type, vendor "
                "ya budget change karke "
                "dekhein."
            ),
        )

    return {
        "intent": "clarification",
        "clarificationType": (
            "no_exact_match"
        ),
        "message": message,
        "options": options,
        "recommendedProducts": [],
    }


def semantic_result_is_low_confidence(
    recommendations: list[
        dict[str, Any]
    ],
) -> bool:
    if not recommendations:
        return True

    top_score = (
        recommendations[0].get(
            "score"
        )
    )

    if not isinstance(
        top_score,
        (int, float),
    ):
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

    threshold = max(
        0.0,
        min(
            threshold,
            1.0,
        ),
    )

    return (
        float(top_score)
        < threshold
    )


def build_low_confidence_clarification(
    filters: dict[str, Any],
    response_language: str,
    search_function: SearchFunction,
) -> dict[str, Any]:
    response = (
        build_no_result_clarification(
            filters=filters,
            response_language=(
                response_language
            ),
            search_function=(
                search_function
            ),
        )
    )

    response[
        "clarificationType"
    ] = (
        "low_semantic_confidence"
    )

    response["message"] = localized(
        response_language,
        (
            "I found products, but their "
            "match confidence is too low. "
            "Please clarify your request or "
            "broaden one filter."
        ),
        (
            "Products mile hain, lekin "
            "unka match confidence bohat "
            "kam hai. Apni request clear "
            "karein ya koi filter broad "
            "karein."
        ),
    )

    return response
