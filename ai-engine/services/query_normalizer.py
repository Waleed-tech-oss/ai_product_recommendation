import re
from difflib import SequenceMatcher
from typing import Any


# Phrase-level synonyms are applied before typo correction.
# Canonical values are intentionally simple English terms because they are
# easier for Groq, CLIP, and PostgreSQL to use consistently.
PHRASE_SYNONYMS = {
    "t shirts": "shirt",
    "t-shirts": "shirt",
    "t shirt": "shirt",
    "tshirt": "shirt",
    "tshirts": "shirt",
    "tees": "shirt",
    "tee": "shirt",
    "sneakers": "shoe",
    "sneaker": "shoe",
    "trainers": "shoe",
    "trainer": "shoe",
    "joggers shoes": "shoe",
    "trousers": "pants",
    "trouser": "pants",
    "snow boards": "snowboard",
    "snow board": "snowboard",
    "mobile phones": "phone",
    "mobile phone": "phone",
    "mobiles": "phone",
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

# These words should never be typo-corrected into a catalog term.
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
    "best",
    "cheap",
    "cheapest",
    "expensive",
    "latest",
}


def _clean(value: str) -> str:
    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            (value or "").lower(),
        )
    )


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(
        None,
        _clean(left),
        _clean(right),
    ).ratio()


def _replace_phrases(text: str) -> tuple[str, list[dict[str, str]]]:
    normalized = text
    corrections: list[dict[str, str]] = []

    for source, target in sorted(
        PHRASE_SYNONYMS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = re.compile(
            rf"\b{re.escape(source)}\b",
            re.IGNORECASE,
        )

        if pattern.search(normalized):
            normalized = pattern.sub(target, normalized)
            corrections.append({
                "from": source,
                "to": target,
                "type": "synonym",
            })

    return normalized, corrections


def _catalog_terms(vocabulary: dict[str, list[str]]) -> list[str]:
    values: list[str] = []

    for key in ("product_types", "vendors"):
        for value in vocabulary.get(key, []):
            cleaned = _clean(str(value))

            if cleaned:
                values.append(cleaned)

    return sorted(
        set(values),
        key=len,
        reverse=True,
    )


def normalize_query_text(
    message: str,
    vocabulary: dict[str, list[str]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """
    Apply safe synonyms and conservative typo correction.

    Example:
        "mujhy snobord dikhao"
        -> "mujhy snowboard dikhao"
    """
    vocabulary = vocabulary or {
        "product_types": [],
        "vendors": [],
    }

    normalized, corrections = _replace_phrases(
        message or ""
    )

    terms = _catalog_terms(vocabulary)

    if not terms:
        return " ".join(normalized.split()), corrections

    tokens = re.findall(
        r"[A-Za-z0-9'-]+|[^A-Za-z0-9'-]+",
        normalized,
    )

    corrected_tokens: list[str] = []

    for token in tokens:
        clean_token = _clean(token)

        if (
            not clean_token
            or len(clean_token) < 4
            or clean_token in TYPO_STOP_WORDS
            or " " in clean_token
        ):
            corrected_tokens.append(token)
            continue

        best_term = None
        best_score = 0.0

        for term in terms:
            if " " in term:
                continue

            if abs(len(term) - len(clean_token)) > 2:
                continue

            score = _similarity(clean_token, term)

            if score > best_score:
                best_term = term
                best_score = score

        # High threshold prevents normal words from being changed accidentally.
        if (
            best_term
            and best_score >= 0.86
            and best_term != clean_token
        ):
            corrected_tokens.append(best_term)
            corrections.append({
                "from": clean_token,
                "to": best_term,
                "type": "typo",
            })
        else:
            corrected_tokens.append(token)

    return (
        " ".join("".join(corrected_tokens).split()),
        corrections,
    )


def _closest_catalog_value(
    value: Any,
    candidates: list[str],
    threshold: float,
) -> tuple[Any, dict[str, str] | None]:
    if value is None:
        return value, None

    original = str(value).strip()

    if not original:
        return value, None

    cleaned_original = _clean(original)

    for candidate in candidates:
        if _clean(candidate) == cleaned_original:
            return candidate, None

    best_candidate = None
    best_score = 0.0

    for candidate in candidates:
        score = _similarity(
            cleaned_original,
            candidate,
        )

        if score > best_score:
            best_candidate = candidate
            best_score = score

    if best_candidate and best_score >= threshold:
        return best_candidate, {
            "from": original,
            "to": best_candidate,
            "type": "catalog_typo",
        }

    return value, None


def normalize_filter_values(
    filters: dict[str, Any],
    vocabulary: dict[str, list[str]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """
    Correct parsed productType/vendor values against real catalog values.
    """
    normalized = dict(filters or {})
    corrections: list[dict[str, str]] = []

    product_type, correction = _closest_catalog_value(
        normalized.get("productType"),
        vocabulary.get("product_types", []),
        threshold=0.72,
    )

    if correction:
        corrections.append(correction)

    normalized["productType"] = product_type

    vendor, correction = _closest_catalog_value(
        normalized.get("vendor"),
        vocabulary.get("vendors", []),
        threshold=0.80,
    )

    if correction:
        corrections.append(correction)

    normalized["vendor"] = vendor

    return normalized, corrections


def detect_product_type_mentions(
    query: str,
    vocabulary: dict[str, list[str]],
) -> list[str]:
    """
    Return distinct catalog product types explicitly mentioned in the query.

    Used to catch ambiguous requests such as:
        "shirt with snowboard"
    """
    normalized_query = f" {_clean(query)} "
    mentions: list[str] = []

    product_types = list(
        vocabulary.get("product_types", [])
    )

    # Useful fallback words even if one is not yet present in the current
    # catalog vocabulary.
    product_types.extend([
        "shirt",
        "shoe",
        "snowboard",
        "pants",
        "dress",
        "jacket",
        "hoodie",
        "bag",
        "phone",
    ])

    for product_type in sorted(
        set(product_types),
        key=lambda item: len(_clean(item)),
        reverse=True,
    ):
        cleaned_type = _clean(product_type)

        if not cleaned_type:
            continue

        pattern = rf"\b{re.escape(cleaned_type)}s?\b"

        if re.search(pattern, normalized_query):
            canonical = str(product_type).strip()

            if canonical.lower() not in {
                item.lower()
                for item in mentions
            }:
                mentions.append(canonical)

    return mentions
