import re
from difflib import SequenceMatcher
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
VALID_ACTIONS = {"new_search", "modify", "reset"}
VALID_RESPONSE_LANGUAGES = {"english", "roman_urdu"}
VALID_RELATIONS = {"none", "single", "multi_list", "ambiguous", "complementary"}

ROMAN_URDU_STRONG_WORDS = {
    "mujhe", "mujhy", "mjy", "dikhao", "dikha", "chahiye", "chahye",
    "sasta", "sasti", "saste", "mehnga", "mehngi", "mehnge", "mahnga",
    "mahngi", "kro", "krdo", "kardo", "wala", "wali", "wale", "kaunsa",
    "konsa", "farq",
}
ROMAN_URDU_COMMON_WORDS = {
    "mere", "liye", "sirf", "aur", "se", "kam", "zyada", "naya", "nayi",
    "naye", "acha", "achi", "achay", "sab", "pichla", "pichli", "dobara",
    "qeemat", "keemat", "sath", "saath", "bhi",
}


def _normalise_language_token(
    token: str,
) -> str:
    """
    Normalise informal spelling without keeping every typo as a
    separate hardcoded entry.

    Examples:
        dikkha -> dikha
        dikhaaa -> dikha
    """
    cleaned = re.sub(
        r"[^a-z]",
        "",
        (token or "").lower(),
    )

    return re.sub(
        r"(.)\1+",
        r"\1",
        cleaned,
    )


def _matches_language_word(
    token: str,
    candidates: set[str],
    threshold: float,
) -> bool:
    normalized_token = (
        _normalise_language_token(
            token
        )
    )

    if not normalized_token:
        return False

    normalized_candidates = {
        _normalise_language_token(
            candidate
        )
        for candidate in candidates
    }

    if (
        normalized_token
        in normalized_candidates
    ):
        return True

    if len(normalized_token) < 3:
        return False

    best_score = max(
        (
            SequenceMatcher(
                None,
                normalized_token,
                candidate,
            ).ratio()
            for candidate
            in normalized_candidates
            if candidate
        ),
        default=0.0,
    )

    return best_score >= threshold


def detect_response_language(
    message: str,
) -> str:
    text = " ".join(
        (message or "")
        .lower()
        .split()
    )

    # Phrase-level Roman Urdu signals for conversational product
    # references. These avoid relying on short ambiguous words alone.
    if re.search(
        r"\b(?:"
        r"pehla|pehli|pehle|"
        r"doosra|doosri|doosre|dusra|dusri|dusre|"
        r"teesra|teesri|teesre|tisra|tisri|tisre|"
        r"chautha|chauthi|panchwa|panchwi|"
        r"aakhri|akhri|"
        r"yaad\s+rakho|yaad\s+rakhna|"
        r"is\s+ki|is\s+ka|is\s+ke|"
        r"us\s+ki|us\s+ka|us\s+ke|"
        r"kya\s+hai|kia\s+hai|"
        r"is\s+jaisa|is\s+jaisi|"
        r"us\s+jaisa|us\s+jaisi"
        r")\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "roman_urdu"

    tokens = re.findall(
        r"[a-zA-Z]+",
        (message or "").lower(),
    )

    # A single strong Roman Urdu signal is enough. This catches
    # informal variants such as "mujy" and "dikkha".
    if any(
        _matches_language_word(
            token,
            ROMAN_URDU_STRONG_WORDS,
            threshold=0.78,
        )
        for token in tokens
    ):
        return "roman_urdu"

    common_matches = sum(
        1
        for token in tokens
        if _matches_language_word(
            token,
            ROMAN_URDU_COMMON_WORDS,
            threshold=0.88,
        )
    )

    if common_matches >= 2:
        return "roman_urdu"

    return "english"


def extract_limit(message: str, default: int = 5) -> int:
    """Extract a result count without mistaking a price for the limit."""
    text = " ".join((message or "").lower().split())
    patterns = [
        r"\b(?:show|find|give|display|recommend|suggest|dikhao|dikha)(?:\s+me|\s+mujhy|\s+mujhe)?\s+(\d{1,2})\b",
        r"\btop\s+(\d{1,2})\b",
        r"\b(\d{1,2})\s+(?:products?|items?|options?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, min(int(match.group(1)), 20))
    return default


def detect_rule_based_intent(message: str) -> str | None:
    text = " ".join((message or "").lower().strip().split())
    if not text:
        return "out_of_context"
    if re.fullmatch(
        r"(hi|hello|hey|salam|assalam[ -]?o[ -]?alaikum|assalamualaikum|good morning|good evening)[!.? ]*",
        text,
    ):
        return "greeting"
    if re.search(
        r"\b(reset|start over|clear (chat|conversation)|new search|forget previous|dobara shuru|phir se shuru|pichli search (reset|clear)|sab clear|chat clear)\b",
        text,
    ):
        return "reset"
    if re.search(
        r"\b(compare|comparison|versus|vs\.?|difference between|farq|muqabla|compare kro|compare karo)\b",
        text,
    ):
        return "compare_products"
    if re.search(
        r"\b(cheapest|lowest[- ]?price(?:d)?|least expensive|most affordable|budget friendly|sasta|sasti|saste|kam qeemat|kam keemat|sab se sasta|sabse sasta)\b",
        text,
    ):
        return "lowest_price"
    if re.search(
        r"\b(most expensive|highest[- ]?price(?:d)?|premium priced|mehnga|mehngi|mehnge|mahnga|mahngi|mahnge|zyada qeemat|zyada keemat|sab se mehnga|sabse mehnga)\b",
        text,
    ):
        return "highest_price"
    if re.search(r"\b(newest|latest|new arrivals?|recently added|naya|nayi|naye)\b", text):
        return "newest_products"
    if re.search(
        r"\b(recommend|recommendation|suggest|best for|good for|what should i buy|which one should i buy|suggest kro|suggest karo|recommend kro|recommend karo|mere liye best|mere liye acha|mere liye achi|konsa acha|kaunsa acha|kya lena chahiye|kia lena chahiye)\b",
        text,
    ):
        return "recommend_products"
    if re.search(
        r"\b(top|popular|best[- ]selling|best products?|sab se achay products|sabse achay products|sab se ache products|sabse ache products)\b",
        text,
    ):
        return "top_products"
    return None


def _normalize_string_list(values: Any, maximum: int = 12) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = " ".join(str(value or "").strip().split())
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        normalized.append(item)
        if len(normalized) >= maximum:
            break
    return normalized


def normalize_intent_result(data: dict[str, Any], user_query: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}

    if data.get("intent") == "shopping":
        data["intent"] = "product_search"

    product_types = _normalize_string_list(data.get("productTypes", []))
    unresolved_types = _normalize_string_list(data.get("unresolvedProductTypes", []))
    data["productTypes"] = product_types
    data["unresolvedProductTypes"] = unresolved_types

    relation = data.get("relation", "none")
    if relation not in VALID_RELATIONS:
        relation = "none"
    data["relation"] = relation

    rule_intent = detect_rule_based_intent(user_query)
    if rule_intent is not None:
        data["intent"] = rule_intent

    if (
        len(product_types) >= 2
        and relation == "multi_list"
        and data.get("intent") != "compare_products"
    ):
        data["intent"] = "multi_product_search"

    if data.get("intent") not in VALID_INTENTS:
        data["intent"] = "out_of_context"
    if data.get("action") not in VALID_ACTIONS:
        data["action"] = "new_search"
    if data["intent"] == "reset":
        data["action"] = "reset"
    if not isinstance(data.get("filters"), dict):
        data["filters"] = {}

    requested_limit = data.get("limit", extract_limit(user_query))
    try:
        requested_limit = int(requested_limit)
    except (TypeError, ValueError):
        requested_limit = extract_limit(user_query)
    data["limit"] = max(1, min(requested_limit, 20))

    data["comparisonTargets"] = _normalize_string_list(
        data.get("comparisonTargets", []), maximum=4
    )

    response_language = data.get("responseLanguage")
    detected_language = detect_response_language(
        user_query
    )

    # A strong Roman Urdu signal from the original customer
    # message takes precedence over an incorrect model label.
    if detected_language == "roman_urdu":
        response_language = "roman_urdu"

    elif (
        response_language
        not in VALID_RESPONSE_LANGUAGES
    ):
        response_language = "english"

    data["responseLanguage"] = response_language

    semantic_query = data.get("semanticQuery")
    if not isinstance(semantic_query, str) or not semantic_query.strip():
        semantic_query = user_query
    data["semanticQuery"] = semantic_query.strip()[:300]

    return data
