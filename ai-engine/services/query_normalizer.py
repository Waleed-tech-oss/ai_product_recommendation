import re
from difflib import SequenceMatcher
from typing import Any


# Stable language/control words only. Product categories and vendors are
# always discovered from the current store catalog.
TYPO_STOP_WORDS = {
    "show", "find", "give", "products", "product", "please", "with",
    "under", "above", "between", "compare", "mujhy", "mujhe", "dikhao",
    "karo", "kro", "sirf", "wale", "wali", "aur", "and", "best", "cheap",
    "cheapest", "expensive", "latest", "sath", "saath", "bhi",
}


def _clean(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _clean(left), _clean(right)).ratio()


def _plural_forms(phrase: str) -> set[str]:
    cleaned = _clean(phrase)
    if not cleaned:
        return set()

    words = cleaned.split()
    final_word = words[-1]
    prefix = words[:-1]
    forms = {final_word}

    if final_word.endswith("y") and len(final_word) > 1 and final_word[-2] not in "aeiou":
        forms.add(f"{final_word[:-1]}ies")
    elif final_word.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(f"{final_word}es")
    else:
        forms.add(f"{final_word}s")

    return {" ".join(prefix + [form]) for form in forms}


def _singular_forms(phrase: str) -> set[str]:
    cleaned = _clean(phrase)
    if not cleaned:
        return set()

    words = cleaned.split()
    final_word = words[-1]
    prefix = words[:-1]
    forms = {final_word}

    if final_word.endswith("ies") and len(final_word) > 3:
        forms.add(f"{final_word[:-3]}y")
    if final_word.endswith("es") and len(final_word) > 2:
        forms.add(final_word[:-2])
    if final_word.endswith("s") and not final_word.endswith("ss") and len(final_word) > 1:
        forms.add(final_word[:-1])

    return {" ".join(prefix + [form]) for form in forms}


def _iter_alias_entries(vocabulary: dict[str, Any]):
    """Support aliases as either a dict or a list of database rows."""
    aliases = vocabulary.get("aliases", {})

    if isinstance(aliases, dict):
        for alias, canonical in aliases.items():
            yield str(alias), str(canonical)
        return

    if not isinstance(aliases, list):
        return

    for item in aliases:
        if not isinstance(item, dict):
            continue
        alias = item.get("alias")
        canonical = (
            item.get("canonical_value")
            or item.get("canonicalValue")
            or item.get("canonical")
            or item.get("target")
        )
        if alias and canonical:
            yield str(alias), str(canonical)


def _catalog_value_maps(
    vocabulary: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    product_map: dict[str, str] = {}
    vendor_map: dict[str, str] = {}

    for product_type in vocabulary.get("product_types", []):
        canonical = " ".join(str(product_type or "").strip().split())
        if not canonical:
            continue
        for form in _plural_forms(canonical) | _singular_forms(canonical):
            product_map[_clean(form)] = canonical

    for vendor in vocabulary.get("vendors", []):
        canonical = " ".join(str(vendor or "").strip().split())
        if canonical:
            vendor_map[_clean(canonical)] = canonical

    for alias, canonical in _iter_alias_entries(vocabulary):
        canonical_key = _clean(canonical)
        if canonical_key in product_map:
            product_map[_clean(alias)] = product_map[canonical_key]
        elif canonical_key in vendor_map:
            vendor_map[_clean(alias)] = vendor_map[canonical_key]

    return product_map, vendor_map


def _replace_dynamic_phrases(
    text: str,
    replacement_map: dict[str, str],
) -> tuple[str, list[dict[str, str]]]:
    normalized = text
    corrections: list[dict[str, str]] = []

    for source, target in sorted(
        replacement_map.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if not source or source == _clean(target):
            continue
        pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
        if not pattern.search(normalized):
            continue
        normalized = pattern.sub(target, normalized)
        corrections.append({
            "from": source,
            "to": target,
            "type": "catalog_alias",
        })

    return normalized, corrections


def _catalog_terms(vocabulary: dict[str, Any]) -> list[str]:
    product_map, vendor_map = _catalog_value_maps(vocabulary)
    return sorted(
        set(product_map.keys()) | set(vendor_map.keys()),
        key=len,
        reverse=True,
    )


def normalize_query_text(
    message: str,
    vocabulary: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    vocabulary = vocabulary or {
        "product_types": [],
        "vendors": [],
        "aliases": {},
    }

    product_map, vendor_map = _catalog_value_maps(vocabulary)
    normalized, corrections = _replace_dynamic_phrases(
        message or "", {**product_map, **vendor_map}
    )

    terms = _catalog_terms(vocabulary)
    if not terms:
        return " ".join(normalized.split()), corrections

    tokens = re.findall(r"[A-Za-z0-9'-]+|[^A-Za-z0-9'-]+", normalized)
    corrected_tokens: list[str] = []
    single_word_terms = [term for term in terms if " " not in term]

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
        for term in single_word_terms:
            if abs(len(term) - len(clean_token)) > 2:
                continue
            score = _similarity(clean_token, term)
            if score > best_score:
                best_term = term
                best_score = score

        if best_term and best_score >= 0.88 and best_term != clean_token:
            canonical = product_map.get(best_term) or vendor_map.get(best_term) or best_term
            corrected_tokens.append(canonical)
            corrections.append({
                "from": clean_token,
                "to": canonical,
                "type": "catalog_typo",
            })
        else:
            corrected_tokens.append(token)

    return " ".join("".join(corrected_tokens).split()), corrections


def _closest_catalog_value(
    value: Any,
    candidates: list[str],
    threshold: float,
    alias_map: dict[str, str] | None = None,
) -> tuple[Any, dict[str, str] | None]:
    if value is None:
        return value, None

    original = " ".join(str(value).strip().split())
    if not original:
        return value, None

    cleaned_original = _clean(original)
    alias_map = alias_map or {}

    direct_alias = alias_map.get(cleaned_original)
    if direct_alias:
        if _clean(direct_alias) == cleaned_original:
            return direct_alias, None
        return direct_alias, {
            "from": original,
            "to": direct_alias,
            "type": "catalog_alias",
        }

    for candidate in candidates:
        if _clean(candidate) == cleaned_original:
            return candidate, None

    best_candidate = None
    best_score = 0.0
    for candidate in candidates:
        candidate_forms = _plural_forms(candidate) | _singular_forms(candidate)
        score = max(_similarity(cleaned_original, form) for form in candidate_forms)
        if score > best_score:
            best_candidate = candidate
            best_score = score

    if best_candidate and best_score >= threshold:
        return best_candidate, {
            "from": original,
            "to": best_candidate,
            "type": "catalog_fuzzy",
        }

    return value, None


def normalize_filter_values(
    filters: dict[str, Any],
    vocabulary: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    normalized = dict(filters or {})
    corrections: list[dict[str, str]] = []
    product_map, vendor_map = _catalog_value_maps(vocabulary)

    product_type, correction = _closest_catalog_value(
        normalized.get("productType"),
        vocabulary.get("product_types", []),
        threshold=0.80,
        alias_map=product_map,
    )
    if correction:
        corrections.append(correction)
    normalized["productType"] = product_type

    vendor, correction = _closest_catalog_value(
        normalized.get("vendor"),
        vocabulary.get("vendors", []),
        threshold=0.84,
        alias_map=vendor_map,
    )
    if correction:
        corrections.append(correction)
    normalized["vendor"] = vendor

    return normalized, corrections


def resolve_requested_product_types(
    values: list[Any],
    vocabulary: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    catalog_types = list(vocabulary.get("product_types", []))
    product_map, _ = _catalog_value_maps(vocabulary)

    resolved: list[str] = []
    unresolved: list[str] = []
    corrections: list[dict[str, str]] = []
    seen_resolved: set[str] = set()
    seen_unresolved: set[str] = set()

    for value in values or []:
        source = " ".join(str(value or "").strip().split())
        if not source:
            continue

        catalog_value, correction = _closest_catalog_value(
            source,
            catalog_types,
            threshold=0.80,
            alias_map=product_map,
        )
        resolved_value = str(catalog_value).strip() if catalog_value is not None else ""
        is_known = any(
            _clean(candidate) == _clean(resolved_value)
            for candidate in catalog_types
        )

        if is_known:
            key = _clean(resolved_value)
            if key not in seen_resolved:
                seen_resolved.add(key)
                resolved.append(resolved_value)
            if correction:
                corrections.append(correction)
            continue

        unresolved_key = _clean(source)
        if unresolved_key and unresolved_key not in seen_unresolved:
            seen_unresolved.add(unresolved_key)
            unresolved.append(source)

    return resolved, unresolved, corrections


def normalize_requested_product_types(
    values: list[Any],
    vocabulary: dict[str, Any],
) -> tuple[list[str], list[dict[str, str]]]:
    resolved, _, corrections = resolve_requested_product_types(values, vocabulary)
    return resolved, corrections


def detect_product_type_mentions(
    query: str,
    vocabulary: dict[str, Any],
) -> list[str]:
    normalized_query = f" {_clean(query)} "
    product_map, _ = _catalog_value_maps(vocabulary)
    mentions: list[str] = []
    seen: set[str] = set()

    for alias, canonical in sorted(
        product_map.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if not alias or not re.search(rf"\b{re.escape(alias)}\b", normalized_query):
            continue
        key = _clean(canonical)
        if key in seen:
            continue
        seen.add(key)
        mentions.append(canonical)

    return mentions


def classify_product_type_request(
    query: str,
    product_types: list[str],
    parser_relation: str | None = None,
) -> str:
    if len(product_types) <= 1:
        return "single"

    if parser_relation in {"multi_list", "ambiguous", "complementary"}:
        return parser_relation

    text = " ".join((query or "").lower().split())

    if re.search(r"\b(compare|versus|vs\.?|farq|muqabla)\b", text):
        return "ambiguous"
    if len(product_types) >= 3 or re.search(r"[,;|/]", query or ""):
        return "multi_list"

    has_with_phrase = bool(
        re.search(
            r"\b(with|sath|saath|ke sath|ke saath|kay sath|kay saath)\b",
            text,
        )
    )
    has_also = bool(re.search(r"\b(also|bhi|dono|all)\b", text))
    if has_with_phrase and not has_also:
        return "ambiguous"
    if re.search(r"\b(for|for use with)\b", text):
        return "complementary"

    has_list_conjunction = bool(re.search(r"\b(and|aur|&)\b", text))
    has_search_instruction = bool(
        re.search(r"\b(show|find|give|dikhao|dikha|chahiye|chahye|search)\b", text)
    )
    if has_list_conjunction or has_search_instruction:
        return "multi_list"
    return "ambiguous"


def suggest_catalog_types(
    unresolved_types: list[str],
    vocabulary: dict[str, Any],
    limit: int = 3,
) -> list[dict[str, Any]]:
    catalog_types = list(vocabulary.get("product_types", []))
    suggestions = []

    for unresolved in unresolved_types:
        ranked = sorted(
            (
                {
                    "value": candidate,
                    "score": round(_similarity(unresolved, candidate), 4),
                }
                for candidate in catalog_types
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        suggestions.append({
            "input": unresolved,
            "suggestions": [
                item["value"] for item in ranked if item["score"] >= 0.45
            ][:limit],
        })

    return suggestions


def should_block_parser_only_catalog_types(
    explicit_mentions: list[str],
    parser_types: list[str],
    unresolved_types: list[str],
) -> bool:
    """
    Block a broad category inferred only by the LLM when the
    customer's explicit product term is not present in the catalog.

    Example:
        Query term: helmets
        Catalog types: accessories
        LLM output:
            productTypes = ["accessories"]
            unresolvedProductTypes = ["helmets"]

    The backend must not search accessories and return unrelated
    products. It must ask an unknown-category clarification.
    """
    return bool(
        unresolved_types
        and parser_types
        and not explicit_mentions
    )

