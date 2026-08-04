import re
from difflib import SequenceMatcher
from typing import Any


PHRASE_SYNONYMS = {
    "t shirts": "shirt",
    "t-shirts": "shirt",
    "t shirt": "shirt",
    "tshirt": "shirt",
    "tshirts": "shirt",
    "shirts": "shirt",
    "tees": "shirt",
    "tee": "shirt",

    "belts": "belt",

    "socks": "sock",

    "baseball caps": "cap",
    "baseball cap": "cap",
    "caps": "cap",
    "hats": "cap",
    "hat": "cap",

    "sneakers": "shoe",
    "sneaker": "shoe",
    "trainers": "shoe",
    "trainer": "shoe",
    "shoes": "shoe",
    "joggers shoes": "shoe",

    "trousers": "pants",
    "trouser": "pants",

    "snow boards": "snowboard",
    "snow board": "snowboard",
    "snowboards": "snowboard",

    "mobile phones": "phone",
    "mobile phone": "phone",
    "mobiles": "phone",
    "phones": "phone",

    "jackets": "jacket",
    "hoodies": "hoodie",
    "bags": "bag",
    "dresses": "dress",

    "kali": "black",
    "kala": "black",
    "kalay": "black",
    "safed": "white",
    "laal": "red",
    "lal": "red",
    "neela": "blue",
    "neeli": "blue",
    "hara": "green",
    "hari": "green",
}


FALLBACK_PRODUCT_TYPES = [
    "shirt",
    "belt",
    "sock",
    "cap",
    "shoe",
    "snowboard",
    "pants",
    "dress",
    "jacket",
    "hoodie",
    "bag",
    "phone",
    "gift card",
]


TYPO_STOP_WORDS = {
    "show",
    "find",
    "give",
    "products",
    "product",
    "please",
    "with",
    "under",
    "above",
    "compare",
    "mujhy",
    "mujhe",
    "dikhao",
    "karo",
    "kro",
    "sirf",
    "wale",
    "wali",
    "aur",
    "and",
    "best",
    "cheap",
    "cheapest",
    "expensive",
    "latest",
    "sath",
    "saath",
    "bhi",
}


def _clean(
    value: str,
) -> str:
    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            (value or "").lower(),
        )
    )


def _similarity(
    left: str,
    right: str,
) -> float:
    return SequenceMatcher(
        None,
        _clean(left),
        _clean(right),
    ).ratio()


def _replace_phrases(
    text: str,
) -> tuple[
    str,
    list[dict[str, str]],
]:
    normalized = text
    corrections: list[
        dict[str, str]
    ] = []

    for source, target in sorted(
        PHRASE_SYNONYMS.items(),
        key=lambda item: len(
            item[0]
        ),
        reverse=True,
    ):
        pattern = re.compile(
            rf"\b{re.escape(source)}\b",
            re.IGNORECASE,
        )

        if pattern.search(
            normalized
        ):
            normalized = pattern.sub(
                target,
                normalized,
            )

            corrections.append({
                "from": source,
                "to": target,
                "type": "synonym",
            })

    return (
        normalized,
        corrections,
    )


def _catalog_terms(
    vocabulary: dict[
        str,
        list[str],
    ],
) -> list[str]:
    values: list[str] = []

    for key in (
        "product_types",
        "vendors",
    ):
        for value in vocabulary.get(
            key,
            [],
        ):
            cleaned = _clean(
                str(value)
            )

            if cleaned:
                values.append(
                    cleaned
                )

    return sorted(
        set(values),
        key=len,
        reverse=True,
    )


def normalize_query_text(
    message: str,
    vocabulary: (
        dict[str, list[str]]
        | None
    ) = None,
) -> tuple[
    str,
    list[dict[str, str]],
]:
    vocabulary = vocabulary or {
        "product_types": [],
        "vendors": [],
    }

    (
        normalized,
        corrections,
    ) = _replace_phrases(
        message or ""
    )

    terms = _catalog_terms(
        vocabulary
    )

    if not terms:
        return (
            " ".join(
                normalized.split()
            ),
            corrections,
        )

    tokens = re.findall(
        (
            r"[A-Za-z0-9'-]+"
            r"|[^A-Za-z0-9'-]+"
        ),
        normalized,
    )

    corrected_tokens: list[str] = []

    for token in tokens:
        clean_token = _clean(
            token
        )

        if (
            not clean_token
            or len(clean_token) < 4
            or clean_token
            in TYPO_STOP_WORDS
            or " " in clean_token
        ):
            corrected_tokens.append(
                token
            )
            continue

        best_term = None
        best_score = 0.0

        for term in terms:
            if " " in term:
                continue

            if (
                abs(
                    len(term)
                    - len(clean_token)
                ) > 2
            ):
                continue

            score = _similarity(
                clean_token,
                term,
            )

            if score > best_score:
                best_term = term
                best_score = score

        if (
            best_term
            and best_score >= 0.86
            and best_term
            != clean_token
        ):
            corrected_tokens.append(
                best_term
            )

            corrections.append({
                "from": clean_token,
                "to": best_term,
                "type": "typo",
            })
        else:
            corrected_tokens.append(
                token
            )

    return (
        " ".join(
            "".join(
                corrected_tokens
            ).split()
        ),
        corrections,
    )


def _closest_catalog_value(
    value: Any,
    candidates: list[str],
    threshold: float,
) -> tuple[
    Any,
    dict[str, str] | None,
]:
    if value is None:
        return value, None

    original = str(
        value
    ).strip()

    if not original:
        return value, None

    cleaned_original = _clean(
        original
    )

    for candidate in candidates:
        if (
            _clean(candidate)
            == cleaned_original
        ):
            return candidate, None

    best_candidate = None
    best_score = 0.0

    for candidate in candidates:
        score = _similarity(
            cleaned_original,
            candidate,
        )

        if score > best_score:
            best_candidate = (
                candidate
            )
            best_score = score

    if (
        best_candidate
        and best_score >= threshold
    ):
        return best_candidate, {
            "from": original,
            "to": best_candidate,
            "type": "catalog_typo",
        }

    return value, None


def normalize_filter_values(
    filters: dict[str, Any],
    vocabulary: dict[
        str,
        list[str],
    ],
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
]:
    normalized = dict(
        filters or {}
    )
    corrections: list[
        dict[str, str]
    ] = []

    (
        product_type,
        correction,
    ) = _closest_catalog_value(
        normalized.get(
            "productType"
        ),
        vocabulary.get(
            "product_types",
            [],
        ),
        threshold=0.72,
    )

    if correction:
        corrections.append(
            correction
        )

    normalized["productType"] = (
        product_type
    )

    (
        vendor,
        correction,
    ) = _closest_catalog_value(
        normalized.get(
            "vendor"
        ),
        vocabulary.get(
            "vendors",
            [],
        ),
        threshold=0.80,
    )

    if correction:
        corrections.append(
            correction
        )

    normalized["vendor"] = vendor

    return (
        normalized,
        corrections,
    )


def normalize_requested_product_types(
    values: list[Any],
    vocabulary: dict[
        str,
        list[str],
    ],
) -> tuple[
    list[str],
    list[dict[str, str]],
]:
    catalog_types = list(
        vocabulary.get(
            "product_types",
            [],
        )
    )

    normalized: list[str] = []
    corrections: list[
        dict[str, str]
    ] = []
    seen: set[str] = set()

    for value in values or []:
        source = _clean(
            str(value or "")
        )

        if not source:
            continue

        source = PHRASE_SYNONYMS.get(
            source,
            source,
        )

        (
            catalog_value,
            correction,
        ) = _closest_catalog_value(
            source,
            catalog_types,
            threshold=0.72,
        )

        final_value = (
            str(catalog_value)
            .strip()
            if catalog_value
            else source
        )

        key = _clean(
            final_value
        )

        if (
            not key
            or key in seen
        ):
            continue

        seen.add(key)
        normalized.append(
            final_value
        )

        if correction:
            corrections.append(
                correction
            )

    return (
        normalized,
        corrections,
    )


def detect_product_type_mentions(
    query: str,
    vocabulary: dict[
        str,
        list[str],
    ],
) -> list[str]:
    normalized_query = (
        f" {_clean(query)} "
    )

    mentions: list[str] = []
    seen: set[str] = set()

    catalog_types = list(
        vocabulary.get(
            "product_types",
            [],
        )
    )

    product_types = (
        catalog_types
        + FALLBACK_PRODUCT_TYPES
    )

    for product_type in sorted(
        set(product_types),
        key=lambda item: len(
            _clean(item)
        ),
        reverse=True,
    ):
        cleaned_type = _clean(
            product_type
        )

        if not cleaned_type:
            continue

        aliases = {
            cleaned_type,
        }

        if cleaned_type.endswith(
            "s"
        ):
            aliases.add(
                cleaned_type[:-1]
            )
        else:
            aliases.add(
                f"{cleaned_type}s"
            )

        matched = any(
            re.search(
                rf"\b{re.escape(alias)}\b",
                normalized_query,
            )
            for alias in aliases
            if alias
        )

        if not matched:
            continue

        canonical = str(
            product_type
        ).strip()

        canonical_key = _clean(
            canonical
        )

        if canonical_key in seen:
            continue

        seen.add(
            canonical_key
        )
        mentions.append(
            canonical
        )

    return mentions


def classify_product_type_request(
    query: str,
    product_types: list[str],
) -> str:
    """
    Returns:
        single
        multi_list
        ambiguous

    Examples:
        shirt, belt, sock, cap
            -> multi_list

        shirts aur caps dikhao
            -> multi_list

        shirt with snowboard
            -> ambiguous
    """
    if len(product_types) <= 1:
        return "single"

    text = " ".join(
        (query or "")
        .lower()
        .split()
    )

    if re.search(
        r"\b(compare|versus|vs\.?|farq|muqabla)\b",
        text,
    ):
        return "ambiguous"

    if len(product_types) >= 3:
        return "multi_list"

    if re.search(
        r"[,;|/]",
        query or "",
    ):
        return "multi_list"

    has_with_phrase = bool(
        re.search(
            r"\b(with|sath|saath|ke sath|ke saath|kay sath|kay saath)\b",
            text,
        )
    )

    has_also = bool(
        re.search(
            r"\b(also|bhi)\b",
            text,
        )
    )

    if (
        has_with_phrase
        and not has_also
    ):
        return "ambiguous"

    has_list_conjunction = bool(
        re.search(
            r"\b(and|aur|&)\b",
            text,
        )
    )

    has_search_instruction = bool(
        re.search(
            r"\b(show|find|give|dikhao|dikha|chahiye|chahye|search)\b",
            text,
        )
    )

    if (
        has_list_conjunction
        or has_search_instruction
    ):
        return "multi_list"

    return "ambiguous"
