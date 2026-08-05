from __future__ import annotations

import os
import re
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            str(value or "").lower(),
        )
    )



_GENERIC_FACET_PATTERNS = (
    re.compile(
        r"^(?:automated|automatic)\s+collection$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:uncategorized|unclassified|default)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:all|all products|products|collection)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:frontpage|front page|home page|homepage)$",
        re.IGNORECASE,
    ),
)


def _facet_is_customer_meaningful(
    facet: dict[str, Any],
) -> bool:
    label = compact_facet_label(
        facet
    )

    if not label:
        return False

    return not any(
        pattern.search(label)
        for pattern
        in _GENERIC_FACET_PATTERNS
    )


def _catalog_type_is_representative(
    profile: dict[str, Any],
) -> bool:
    """
    A product type is already specific enough when most real product
    titles naturally contain that type.

    Examples:
    - Snowboard -> Complete Snowboard, Hydrogen Snowboard: representative.
    - Accessories -> Selling Plans Ski Wax: not representative.

    No product/category names are hardcoded.
    """
    try:
        match_ratio = float(
            profile.get(
                "titleMatchRatio"
            )
            or 0.0
        )
    except (
        TypeError,
        ValueError,
    ):
        match_ratio = 0.0

    try:
        threshold = float(
            os.getenv(
                "PRODUCT_TYPE_TITLE_MATCH_THRESHOLD",
                "0.60",
            )
        )
    except ValueError:
        threshold = 0.60

    threshold = max(
        0.0,
        min(
            threshold,
            1.0,
        ),
    )

    return match_ratio >= threshold


def _singular_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return f"{token[:-3]}y"
    if token.endswith("es") and token.endswith(
        ("ses", "xes", "zes", "ches", "shes")
    ):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _token_signature(value: Any) -> set[str]:
    return {
        _singular_token(token)
        for token in _clean(value).split()
        if token
    }


def compact_facet_label(
    facet: dict[str, Any],
) -> str:
    label = " ".join(
        str(facet.get("label") or facet.get("value") or "")
        .strip()
        .split()
    )

    if (
        facet.get("type") == "taxonomy"
        and ">" in label
    ):
        label = label.split(">")[-1].strip()

    return label


def prepare_catalog_facets(
    profile: dict[str, Any],
    limit: int = 6,
) -> list[dict[str, Any]]:
    """
    Convert raw taxonomy/collection facets into concise, deduplicated
    customer-facing options. No category names are hardcoded.
    """
    prepared: list[dict[str, Any]] = []
    seen_labels: set[str] = set()

    raw_facets = (
        profile.get(
            "facets",
            [],
        )
        or []
    )

    meaningful_facets = [
        facet
        for facet
        in raw_facets
        if _facet_is_customer_meaningful(
            facet
        )
    ]

    # Keep both meaningful taxonomy and collection facets. The matching
    # layer may use a collection phrase explicitly typed by the customer,
    # while the clarification decision still treats taxonomy as the
    # stronger structural signal.
    for facet in meaningful_facets:
        label = compact_facet_label(facet)
        label_key = _clean(label)

        if not label_key or label_key in seen_labels:
            continue

        seen_labels.add(label_key)

        prepared.append({
            "type": facet.get("type"),
            "label": label,
            "value": facet.get("value"),
            "count": int(facet.get("count") or 0),
        })

    prepared.sort(
        key=lambda item: (
            -int(item.get("count") or 0),
            0 if item.get("type") == "taxonomy" else 1,
            str(item.get("label") or "").lower(),
        )
    )

    return prepared[:max(1, min(int(limit), 10))]


def _facet_is_equivalent_to_product_type(
    product_type: str,
    facet_label: str,
) -> bool:
    type_tokens = _token_signature(product_type)
    facet_tokens = _token_signature(facet_label)

    if not type_tokens or not facet_tokens:
        return False

    if (
        type_tokens.issubset(
            facet_tokens
        )
        or facet_tokens.issubset(
            type_tokens
        )
    ):
        return True

    # Handle catalog terms such as "giftcard" versus "Gift Card".
    compact_type = "".join(
        sorted(type_tokens)
    )
    compact_facet = "".join(
        sorted(facet_tokens)
    )

    return (
        compact_type
        in compact_facet
        or compact_facet
        in compact_type
    )


def query_requests_show_all(
    query: str,
) -> bool:
    text = _clean(query)

    patterns = (
        r"\bshow(?: me)? all\b",
        r"\blist all\b",
        r"\bdisplay all\b",
        r"\bsab(?: products?)? dikha(?:o)?\b",
        r"\btamam(?: products?)? dikha(?:o)?\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def match_query_to_catalog_facet(
    query: str,
    product_type: str,
    facets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Automatically apply a real catalog facet when the customer already
    typed it, e.g. "winter sports accessories".
    """
    normalized_query = _clean(query)
    if not normalized_query:
        return None

    matches: list[
        tuple[
            int,
            int,
            int,
            dict[str, Any],
        ]
    ] = []

    for facet in facets:
        raw_label = str(
            facet.get("value")
            or facet.get("label")
            or ""
        )

        compact_label = _clean(
            compact_facet_label(
                facet
            )
        )
        full_label = _clean(
            raw_label
        )

        candidates: list[
            tuple[str, int]
        ] = [
            (
                compact_label,
                3,
            ),
            (
                full_label,
                2,
            ),
        ]

        if facet.get("type") == "taxonomy":
            candidates.extend(
                (
                    _clean(segment),
                    1,
                )
                for segment
                in raw_label.split(">")
            )

        for (
            candidate,
            match_priority,
        ) in candidates:
            if (
                not candidate
                or candidate
                == _clean(
                    product_type
                )
                or len(candidate) < 4
            ):
                continue

            if candidate in normalized_query:
                source_priority = (
                    1
                    if facet.get(
                        "type"
                    )
                    == "collection"
                    else 0
                )

                matches.append(
                    (
                        len(candidate),
                        match_priority,
                        source_priority,
                        facet,
                    )
                )
                break

    if not matches:
        return None

    matches.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        ),
        reverse=True,
    )

    return matches[0][3]


def should_clarify_broad_category(
    *,
    product_type: str,
    profile: dict[str, Any],
    active_filters: dict[str, Any],
    original_query: str,
    bypass: bool = False,
) -> bool:
    """
    Detect a broad product type from actual catalog diversity.

    Clarification is shown when:
    - the customer did not explicitly request "show all";
    - no taxonomy/collection refinement is already active; and
    - the catalog exposes multiple distinct facets, or one facet whose
      label is meaningfully more specific than the product type.
    """
    if (
        bypass
        or query_requests_show_all(original_query)
        or active_filters.get("taxonomyCategory")
        or active_filters.get("collection")
        or active_filters.get("handle")
    ):
        return False

    # Do not interrupt a concrete product type merely because products
    # also belong to marketing/demo collections. Product-title alignment
    # is derived from the live catalog.
    if _catalog_type_is_representative(
        profile
    ):
        return False

    facets = prepare_catalog_facets(
        profile,
        limit=10,
    )

    if not facets:
        return False

    try:
        min_products = max(
            1,
            int(
                os.getenv(
                    "BROAD_CATEGORY_MIN_PRODUCTS",
                    "1",
                )
            ),
        )
    except ValueError:
        min_products = 1

    if int(profile.get("productCount") or 0) < min_products:
        return False

    structural_facets = [
        facet
        for facet in facets
        if facet.get("type")
        in {
            "taxonomy",
            "collection",
        }
    ]

    if structural_facets:
        taxonomy_facets = [
            facet
            for facet
            in structural_facets
            if facet.get("type")
            == "taxonomy"
        ]

        if taxonomy_facets:
            # A single meaningful taxonomy path can reveal that the
            # merchant's product type is too broad.
            return any(
                not _facet_is_equivalent_to_product_type(
                    product_type,
                    facet.get(
                        "label"
                    )
                    or "",
                )
                for facet
                in taxonomy_facets
            )

        collection_facets = [
            facet
            for facet
            in structural_facets
            if facet.get("type")
            == "collection"
        ]

        # A single merchant collection is often promotional or
        # operational rather than a true category split.
        return len(
            collection_facets
        ) >= 2

    product_facets = [
        facet
        for facet in facets
        if facet.get("type")
        == "product"
    ]

    if not product_facets:
        return False

    mismatched_product_titles = [
        facet
        for facet in product_facets
        if not _facet_is_equivalent_to_product_type(
            product_type,
            facet.get("label") or "",
        )
    ]

    # Example:
    # product_type = Accessories
    # title = Selling Plans Ski Wax
    #
    # The catalog classification is too broad to silently treat the
    # title as an obvious category result. Ask the customer to choose
    # the actual product or explicitly browse all.
    mismatch_ratio = (
        len(mismatched_product_titles)
        / len(product_facets)
    )

    return mismatch_ratio >= 0.5
