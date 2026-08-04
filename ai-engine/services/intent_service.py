import re
from typing import Any


VALID_INTENTS = {
    "product_search",
    "multi_product_search",
    "top_products",
    "lowest_price",
    "highest_price",
    "newest_products",
    "compare_products",
    "recommend_products",
    "greeting",
    "reset",
    "out_of_context",
}

VALID_ACTIONS = {
    "new_search",
    "modify",
    "reset",
}

VALID_RESPONSE_LANGUAGES = {
    "english",
    "roman_urdu",
}


ROMAN_URDU_STRONG_WORDS = {
    "mujhe",
    "mujhy",
    "mjy",
    "dikhao",
    "dikha",
    "chahiye",
    "chahye",
    "sasta",
    "sasti",
    "saste",
    "mehnga",
    "mehngi",
    "mehnge",
    "mahnga",
    "mahngi",
    "kro",
    "krdo",
    "kardo",
    "wala",
    "wali",
    "wale",
    "kaunsa",
    "konsa",
    "farq",
}

ROMAN_URDU_COMMON_WORDS = {
    "mere",
    "liye",
    "sirf",
    "aur",
    "se",
    "kam",
    "zyada",
    "naya",
    "nayi",
    "naye",
    "acha",
    "achi",
    "achay",
    "sab",
    "pichla",
    "pichli",
    "dobara",
    "qeemat",
    "keemat",
    "sath",
    "saath",
    "bhi",
}


def detect_response_language(
    message: str,
) -> str:
    tokens = set(
        re.findall(
            r"[a-zA-Z]+",
            (message or "").lower(),
        )
    )

    if tokens.intersection(
        ROMAN_URDU_STRONG_WORDS
    ):
        return "roman_urdu"

    if len(
        tokens.intersection(
            ROMAN_URDU_COMMON_WORDS
        )
    ) >= 2:
        return "roman_urdu"

    return "english"


def extract_limit(
    message: str,
    default: int = 5,
) -> int:
    match = re.search(
        r"\b(\d{1,2})\b",
        message or "",
    )

    if not match:
        return default

    return max(
        1,
        min(
            int(match.group(1)),
            20,
        ),
    )


def detect_rule_based_intent(
    message: str,
) -> str | None:
    text = " ".join(
        (message or "")
        .lower()
        .strip()
        .split()
    )

    if not text:
        return "out_of_context"

    if re.fullmatch(
        r"(hi|hello|hey|salam|assalam[ -]?o[ -]?alaikum|"
        r"assalamualaikum|good morning|good evening)[!.? ]*",
        text,
    ):
        return "greeting"

    if re.search(
        r"\b(reset|start over|clear (chat|conversation)|new search|"
        r"forget previous|dobara shuru|phir se shuru|"
        r"pichli search (reset|clear)|sab clear|chat clear)\b",
        text,
    ):
        return "reset"

    if re.search(
        r"\b(compare|comparison|versus|vs\.?|difference between|"
        r"farq|muqabla|compare kro|compare karo)\b",
        text,
    ):
        return "compare_products"

    if re.search(
        r"\b(cheapest|lowest[- ]?price(?:d)?|least expensive|"
        r"most affordable|budget friendly|sasta|sasti|saste|"
        r"kam qeemat|kam keemat|sab se sasta|sabse sasta)\b",
        text,
    ):
        return "lowest_price"

    if re.search(
        r"\b(most expensive|highest[- ]?price(?:d)?|premium priced|"
        r"mehnga|mehngi|mehnge|mahnga|mahngi|mahnge|"
        r"zyada qeemat|zyada keemat|sab se mehnga|sabse mehnga)\b",
        text,
    ):
        return "highest_price"

    if re.search(
        r"\b(newest|latest|new arrivals?|recently added|"
        r"naya|nayi|naye)\b",
        text,
    ):
        return "newest_products"

    if re.search(
        r"\b(recommend|recommendation|suggest|best for|good for|"
        r"what should i buy|which one should i buy|"
        r"suggest kro|suggest karo|recommend kro|recommend karo|"
        r"mere liye best|mere liye acha|mere liye achi|"
        r"konsa acha|kaunsa acha|kya lena chahiye|kia lena chahiye)\b",
        text,
    ):
        return "recommend_products"

    if re.search(
        r"\b(top|popular|best[- ]selling|best products?|"
        r"sab se achay products|sabse achay products|"
        r"sab se ache products|sabse ache products)\b",
        text,
    ):
        return "top_products"

    return None


def _normalize_string_list(
    values: Any,
    maximum: int = 12,
) -> list[str]:
    if not isinstance(values, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        item = " ".join(
            str(value or "")
            .strip()
            .split()
        )

        if not item:
            continue

        key = item.lower()

        if key in seen:
            continue

        seen.add(key)
        normalized.append(item)

        if len(normalized) >= maximum:
            break

    return normalized


def normalize_intent_result(
    data: dict[str, Any],
    user_query: str,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}

    if data.get("intent") == "shopping":
        data["intent"] = (
            "product_search"
        )

    product_types = (
        _normalize_string_list(
            data.get(
                "productTypes",
                [],
            )
        )
    )

    data["productTypes"] = (
        product_types
    )

    rule_intent = (
        detect_rule_based_intent(
            user_query
        )
    )

    if rule_intent is not None:
        data["intent"] = (
            rule_intent
        )

    # A structured list of two or more categories is a
    # multi-category search unless the user is comparing products.
    if (
        len(product_types) >= 2
        and data.get("intent")
        != "compare_products"
    ):
        data["intent"] = (
            "multi_product_search"
        )

    if (
        data.get("intent")
        not in VALID_INTENTS
    ):
        data["intent"] = (
            "out_of_context"
        )

    if (
        data.get("action")
        not in VALID_ACTIONS
    ):
        data["action"] = (
            "new_search"
        )

    if data["intent"] == "reset":
        data["action"] = "reset"

    if not isinstance(
        data.get("filters"),
        dict,
    ):
        data["filters"] = {}

    requested_limit = data.get(
        "limit",
        extract_limit(user_query),
    )

    try:
        requested_limit = int(
            requested_limit
        )
    except (
        TypeError,
        ValueError,
    ):
        requested_limit = (
            extract_limit(
                user_query
            )
        )

    data["limit"] = max(
        1,
        min(
            requested_limit,
            20,
        ),
    )

    data["comparisonTargets"] = (
        _normalize_string_list(
            data.get(
                "comparisonTargets",
                [],
            ),
            maximum=4,
        )
    )

    response_language = (
        data.get(
            "responseLanguage"
        )
    )

    if (
        response_language
        not in VALID_RESPONSE_LANGUAGES
    ):
        response_language = (
            detect_response_language(
                user_query
            )
        )

    data["responseLanguage"] = (
        response_language
    )

    semantic_query = data.get(
        "semanticQuery"
    )

    if (
        not isinstance(
            semantic_query,
            str,
        )
        or not semantic_query.strip()
    ):
        semantic_query = user_query

    data["semanticQuery"] = (
        semantic_query
        .strip()[:300]
    )

    return data
