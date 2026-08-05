from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


MAX_REMEMBERED_PRODUCTS = 12
MAX_RESULT_HISTORY = 5


ORDINAL_PATTERNS: list[
    tuple[int | str, re.Pattern]
] = [
    (
        0,
        re.compile(
            r"\b(?:first|1st|pehla|pehli|pehle)"
            r"(?:\s+(?:one|product|item|wala|wali))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        1,
        re.compile(
            r"\b(?:second|2nd|doosra|doosri|dusra|dusri|dosra|dosri)"
            r"(?:\s+(?:one|product|item|wala|wali))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        2,
        re.compile(
            r"\b(?:third|3rd|teesra|teesri|tisra|tisri)"
            r"(?:\s+(?:one|product|item|wala|wali))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        3,
        re.compile(
            r"\b(?:fourth|4th|chautha|chauthi)"
            r"(?:\s+(?:one|product|item|wala|wali))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        4,
        re.compile(
            r"\b(?:fifth|5th|panchwa|panchwi)"
            r"(?:\s+(?:one|product|item|wala|wali))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "last",
        re.compile(
            r"\b(?:last|final|akhri|aakhri)"
            r"(?:\s+(?:one|product|item|wala|wali))?\b",
            re.IGNORECASE,
        ),
    ),
]


DEICTIC_PATTERN = re.compile(
    r"\b(?:"
    r"this one|that one|this product|that product|"
    r"selected product|"
    r"yeh wala|ye wala|yeh product|ye product|"
    r"is wala|is product|is ki|is ka|is ke|"
    r"woh wala|wo wala|us wala|us product|"
    r"us ki|us ka|us ke"
    r")\b",
    re.IGNORECASE,
)

CHEAPEST_PATTERN = re.compile(
    r"\b(?:"
    r"cheapest|lowest[- ]priced|"
    r"sab\s*se\s*sasta|sabse\s*sasta|sasta\s+wala"
    r")\b",
    re.IGNORECASE,
)

EXPENSIVE_PATTERN = re.compile(
    r"\b(?:"
    r"most expensive|highest[- ]priced|"
    r"sab\s*se\s*mehnga|sabse\s*mehnga|mehnga\s+wala"
    r")\b",
    re.IGNORECASE,
)

SELECTION_PATTERN = re.compile(
    r"\b(?:"
    r"select|choose|pick|remember|save|"
    r"yaad\s+rakho|yaad\s+rakhna|"
    r"select\s+karo|select\s+kro|"
    r"choose\s+karo|choose\s+kro"
    r")\b",
    re.IGNORECASE,
)

SIMILAR_PATTERN = re.compile(
    r"\b(?:"
    r"similar|more\s+like|like\s+this|like\s+that|"
    r"is\s+jaisa|is\s+jaisi|us\s+jaisa|us\s+jaisi|"
    r"(?:pehle|pehli|pehla|doosre|doosri|doosra|"
    r"dusre|dusri|dusra|teesre|teesri|teesra|"
    r"tisre|tisri|tisra|chauth[eai]|panchw[aei])"
    r"\s+jais[ai]|"
    r"aisa\s+aur|aisi\s+aur|"
    r"same\s+jaisa|same\s+jaisi"
    r")\b",
    re.IGNORECASE,
)

DETAIL_PATTERN = re.compile(
    r"\b(?:"
    r"price|cost|how much|available|availability|stock|"
    r"kitne\s+ka|kitni\s+ki|qeemat|keemat|"
    r"available\s+hai|stock\s+mein"
    r")\b",
    re.IGNORECASE,
)

COMPARE_PATTERN = re.compile(
    r"\b(?:"
    r"compare|comparison|versus|vs|"
    r"muqabla|farq"
    r")\b",
    re.IGNORECASE,
)


def _clean_text(
    value: Any,
) -> str:
    return " ".join(
        str(value or "")
        .strip()
        .split()
    )


def _product_identity(
    product: dict[str, Any],
) -> str:
    for key in (
        "shopify_id",
        "id",
        "handle",
    ):
        value = _clean_text(
            product.get(key)
        )

        if value:
            return (
                f"{key}:{value.lower()}"
            )

    return (
        "title:"
        + _clean_text(
            product.get("title")
        ).lower()
    )


def product_snapshot(
    product: dict[str, Any],
    position: int | None = None,
) -> dict[str, Any]:
    """
    Store only safe product facts required by conversational follow-ups.
    Embeddings and internal search documents are intentionally excluded.
    """
    allowed_keys = (
        "id",
        "shopify_id",
        "shop_domain",
        "title",
        "handle",
        "vendor",
        "product_type",
        "taxonomy_category_name",
        "taxonomy_category_full_name",
        "image_url",
        "image_alt_text",
        "sku",
        "price",
        "currency_code",
        "available_for_sale",
        "variants",
        "rankingMode",
        "score",
    )

    snapshot = {
        key: deepcopy(
            product.get(key)
        )
        for key in allowed_keys
        if product.get(key)
        is not None
    }

    if position is not None:
        snapshot[
            "displayPosition"
        ] = position

    return snapshot


def build_product_snapshots(
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    snapshots: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    for index, product in enumerate(
        products or [],
        start=1,
    ):
        snapshot = product_snapshot(
            product,
            position=index,
        )

        identity = _product_identity(
            snapshot
        )

        if (
            not snapshot.get("title")
            or identity in seen
        ):
            continue

        seen.add(identity)
        snapshots.append(
            snapshot
        )

        if (
            len(snapshots)
            >= MAX_REMEMBERED_PRODUCTS
        ):
            break

    return snapshots


def remember_product_results(
    state: dict[str, Any] | None,
    products: list[dict[str, Any]],
    *,
    query: str,
    intent: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(
        state
        if isinstance(state, dict)
        else {}
    )

    snapshots = (
        build_product_snapshots(
            products
        )
    )

    if not snapshots:
        return updated

    updated[
        "last_products"
    ] = snapshots
    updated[
        "last_query"
    ] = _clean_text(query)
    updated[
        "last_intent"
    ] = _clean_text(intent)
    updated[
        "last_filters"
    ] = deepcopy(
        filters
        if isinstance(filters, dict)
        else {}
    )

    history = updated.get(
        "result_history"
    )

    if not isinstance(
        history,
        list,
    ):
        history = []

    history.append({
        "query": (
            _clean_text(query)
        ),
        "intent": (
            _clean_text(intent)
        ),
        "products": snapshots,
    })

    updated[
        "result_history"
    ] = history[
        -MAX_RESULT_HISTORY:
    ]

    selected = updated.get(
        "selected_product"
    )

    if isinstance(
        selected,
        dict,
    ):
        selected_identity = (
            _product_identity(
                selected
            )
        )

        for product in snapshots:
            if (
                _product_identity(
                    product
                )
                == selected_identity
            ):
                updated[
                    "selected_product"
                ] = product
                break

    return updated


def select_product(
    state: dict[str, Any] | None,
    product: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(
        state
        if isinstance(state, dict)
        else {}
    )

    updated[
        "selected_product"
    ] = product_snapshot(
        product,
        position=(
            product.get(
                "displayPosition"
            )
        ),
    )

    return updated


def has_product_reference(
    query: str,
) -> bool:
    text = query or ""

    if DEICTIC_PATTERN.search(
        text
    ):
        return True

    if CHEAPEST_PATTERN.search(
        text
    ):
        return True

    if EXPENSIVE_PATTERN.search(
        text
    ):
        return True

    if re.search(
        r"\b(?:product|item|number|no\.?)\s*[1-9]\b",
        text,
        flags=re.IGNORECASE,
    ):
        return True

    return any(
        pattern.search(text)
        for _, pattern
        in ORDINAL_PATTERNS
    )


def detect_product_selection_request(
    query: str,
) -> bool:
    return bool(
        SELECTION_PATTERN.search(
            query or ""
        )
        and has_product_reference(
            query
        )
    )


def detect_similar_product_request(
    query: str,
) -> bool:
    return bool(
        SIMILAR_PATTERN.search(
            query or ""
        )
    )


def detect_product_detail_request(
    query: str,
) -> bool:
    text = query or ""

    return bool(
        DETAIL_PATTERN.search(
            text
        )
        and has_product_reference(
            text
        )
        and not COMPARE_PATTERN.search(
            text
        )
    )


def _numeric_reference_matches(
    query: str,
) -> list[
    tuple[int, int, str]
]:
    matches: list[
        tuple[int, int, str]
    ] = []

    pattern = re.compile(
        r"\b(?:product|item|number|no\.?)\s*([1-9][0-9]*)\b",
        re.IGNORECASE,
    )

    for match in pattern.finditer(
        query or ""
    ):
        matches.append(
            (
                match.start(),
                int(
                    match.group(1)
                )
                - 1,
                match.group(0),
            )
        )

    return matches


def _price_value(
    product: dict[str, Any],
) -> float | None:
    try:
        return float(
            product.get("price")
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def resolve_product_references(
    query: str,
    last_products: list[
        dict[str, Any]
    ] | None,
    selected_product: (
        dict[str, Any]
        | None
    ) = None,
) -> dict[str, Any]:
    products = [
        product
        for product
        in (
            last_products
            if isinstance(
                last_products,
                list,
            )
            else []
        )
        if isinstance(
            product,
            dict,
        )
    ]

    candidates: list[
        tuple[int, int | str, str]
    ] = []

    for reference, pattern in (
        ORDINAL_PATTERNS
    ):
        for match in pattern.finditer(
            query or ""
        ):
            candidates.append(
                (
                    match.start(),
                    reference,
                    match.group(0),
                )
            )

    candidates.extend(
        _numeric_reference_matches(
            query
        )
    )

    if CHEAPEST_PATTERN.search(
        query or ""
    ):
        candidates.append(
            (
                (
                    CHEAPEST_PATTERN.search(
                        query or ""
                    )
                    .start()
                ),
                "cheapest",
                "cheapest",
            )
        )

    if EXPENSIVE_PATTERN.search(
        query or ""
    ):
        candidates.append(
            (
                (
                    EXPENSIVE_PATTERN.search(
                        query or ""
                    )
                    .start()
                ),
                "expensive",
                "most expensive",
            )
        )

    candidates.sort(
        key=lambda item: item[0]
    )

    resolved: list[
        dict[str, Any]
    ] = []
    unresolved: list[str] = []
    detected: list[str] = []
    used_identities: set[str] = set()

    for _, reference, label in (
        candidates
    ):
        detected.append(label)

        product = None

        if reference == "last":
            if products:
                product = products[-1]

        elif reference in {
            "cheapest",
            "expensive",
        }:
            priced_products = [
                (
                    _price_value(
                        candidate
                    ),
                    candidate,
                )
                for candidate
                in products
                if _price_value(
                    candidate
                )
                is not None
            ]

            if priced_products:
                chooser = (
                    min
                    if reference
                    == "cheapest"
                    else max
                )

                product = chooser(
                    priced_products,
                    key=lambda item: (
                        item[0]
                    ),
                )[1]

        elif (
            isinstance(
                reference,
                int,
            )
            and 0
            <= reference
            < len(products)
        ):
            product = (
                products[
                    reference
                ]
            )

        if product is None:
            unresolved.append(label)
            continue

        identity = _product_identity(
            product
        )

        if identity in used_identities:
            continue

        used_identities.add(
            identity
        )
        resolved.append(
            product_snapshot(
                product,
                position=(
                    product.get(
                        "displayPosition"
                    )
                ),
            )
        )

    deictic_requested = bool(
        DEICTIC_PATTERN.search(
            query or ""
        )
        or (
            detect_similar_product_request(
                query
            )
            and not candidates
        )
    )

    if (
        not resolved
        and deictic_requested
    ):
        if isinstance(
            selected_product,
            dict,
        ):
            resolved.append(
                product_snapshot(
                    selected_product,
                    position=(
                        selected_product.get(
                            "displayPosition"
                        )
                    ),
                )
            )
            detected.append(
                "selected product"
            )

        elif len(products) == 1:
            resolved.append(
                product_snapshot(
                    products[0],
                    position=1,
                )
            )
            detected.append(
                "only displayed product"
            )

        else:
            unresolved.append(
                "selected product"
            )

    return {
        "resolved": resolved,
        "unresolved": unresolved,
        "detectedReferences": (
            detected
        ),
        "availableCount": (
            len(products)
        ),
    }


def hydrate_memory_products(
    snapshots: list[
        dict[str, Any]
    ],
    catalog_products: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    by_identity: dict[
        str,
        dict[str, Any]
    ] = {}

    for product in (
        catalog_products
        or []
    ):
        if not isinstance(
            product,
            dict,
        ):
            continue

        by_identity[
            _product_identity(
                product
            )
        ] = product

    hydrated: list[
        dict[str, Any]
    ] = []

    for snapshot in (
        snapshots
        or []
    ):
        identity = (
            _product_identity(
                snapshot
            )
        )

        product = by_identity.get(
            identity
        )

        hydrated.append(
            product
            if product is not None
            else snapshot
        )

    return hydrated


def reference_option_payloads(
    products: list[
        dict[str, Any]
    ],
    response_language: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    options: list[
        dict[str, Any]
    ] = []

    roman_labels = [
        "Pehla",
        "Doosra",
        "Teesra",
        "Chautha",
        "Panchwa",
    ]

    english_labels = [
        "First",
        "Second",
        "Third",
        "Fourth",
        "Fifth",
    ]

    for index, product in enumerate(
        (products or [])[:limit]
    ):
        title = _clean_text(
            product.get("title")
        )

        if not title:
            continue

        label_prefix = (
            roman_labels[index]
            if response_language
            == "roman_urdu"
            else english_labels[index]
        )

        message = (
            f"{label_prefix} wala select karo"
            if response_language
            == "roman_urdu"
            else (
                f"Select the "
                f"{label_prefix.lower()} product"
            )
        )

        options.append({
            "label": (
                f"{label_prefix}: {title}"
            ),
            "message": message,
            "position": index + 1,
        })

    return options
