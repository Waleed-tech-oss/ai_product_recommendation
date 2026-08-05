# ai-engine/routes/chat.py
import re

from fastapi import (
    APIRouter,
    Query,
)
from pydantic import BaseModel
from typing import Any

from database.postgres import (
    get_all_shopify_products,
    get_catalog_vocabulary,
    get_chat_suggestions,
    get_filtered_products,
    get_grouped_products_by_types,
    get_product_type_profile,
)
from database.chat_session import (
    delete_session,
    get_conversation_state,
    get_session,
    save_conversation_state,
    save_session,
)

from services.chat_service import (
    parse_user_query,
)
from services.clarification_service import (
    build_broad_category_clarification,
    build_low_confidence_clarification,
    build_multiple_type_clarification,
    build_no_result_clarification,
    build_unknown_type_clarification,
    semantic_result_is_low_confidence,
)
from services.catalog_intelligence_service import (
    match_query_to_catalog_facet,
    prepare_catalog_facets,
    should_clarify_broad_category,
)
from services.clip_service import (
    generate_text_embedding,
)
from services.comparison_service import (
    build_product_comparison,
    extract_comparison_targets,
    match_comparison_products,
)
from services.conversation_memory_service import (
    detect_product_detail_request,
    detect_product_selection_request,
    detect_similar_product_request,
    hydrate_memory_products,
    reference_option_payloads,
    remember_product_results,
    resolve_product_references,
    select_product,
)
from services.filter_merger import (
    merge_filters,
)
from services.filter_normalizer import (
    normalize_filters,
)
from services.groq_service import (
    generate_comparison_summary,
    generate_explanations,
)
from services.intent_service import (
    detect_response_language,
)
from services.query_normalizer import (
    classify_product_type_request,
    detect_product_type_mentions,
    normalize_filter_values,
    normalize_query_text,
    resolve_requested_product_types,
    should_block_parser_only_catalog_types,
    suggest_catalog_types,
)
from services.recommendation_service import (
    find_more_like_shopify_product,
    find_similar_products,
)


router = APIRouter(
    prefix="/chat",
    tags=[
        "Shopping Assistant"
    ],
)


class ChatRequest(
    BaseModel
):
    sessionId: str
    message: str
    shopDomain: str | None = None
    clarificationAction: (
        str | None
    ) = None
    clarificationFilters: (
        dict[str, Any] | None
    ) = None
    bypassBroadCategoryClarification: (
        bool
    ) = False


def localized_message(
    response_language: str,
    english: str,
    roman_urdu: str,
) -> str:
    return (
        roman_urdu
        if response_language
        == "roman_urdu"
        else english
    )


def public_products(
    products: list[dict],
) -> list[dict]:
    return [
        {
            key: value
            for key, value
            in product.items()
            if key
            not in {
                "embedding",
                "image_embedding",
                "text_embedding",
                "search_document",
            }
        }
        for product in products
    ]



def _remember_products(
    *,
    session_id: str,
    products: list[dict],
    query: str,
    intent: str,
    filters: dict | None,
) -> None:
    if not products:
        return

    state = (
        get_conversation_state(
            session_id
        )
        or {}
    )

    updated_state = (
        remember_product_results(
            state,
            public_products(
                products
            ),
            query=query,
            intent=intent,
            filters=filters,
        )
    )

    save_conversation_state(
        session_id,
        updated_state,
        filters=(
            filters
            if isinstance(
                filters,
                dict,
            )
            else {}
        ),
        last_query=query,
    )


def _reference_clarification(
    *,
    response_language: str,
    last_products: list[dict],
    unresolved: list[str] | None = None,
) -> dict:
    missing_text = ", ".join(
        unresolved or []
    )

    return {
        "intent": "clarification",
        "clarificationType": (
            "product_reference_required"
        ),
        "responseLanguage": (
            response_language
        ),
        "message": localized_message(
            response_language,
            (
                "I could not identify the referenced product"
                + (
                    f" ({missing_text})"
                    if missing_text
                    else ""
                )
                + ". Please select one of the last displayed products."
            ),
            (
                "Main referenced product identify nahi kar saka"
                + (
                    f" ({missing_text})"
                    if missing_text
                    else ""
                )
                + ". Pichlay results mein se product select karein."
            ),
        ),
        "options": (
            reference_option_payloads(
                last_products,
                response_language,
            )
        ),
        "recommendedProducts": [],
    }


def _product_detail_message(
    product: dict,
    response_language: str,
) -> str:
    title = (
        product.get("title")
        or "Product"
    )
    price = product.get(
        "price"
    )
    currency = (
        product.get(
            "currency_code"
        )
        or ""
    )

    if price is None:
        price_text = (
            "price available nahi hai"
            if response_language
            == "roman_urdu"
            else "the price is unavailable"
        )
    else:
        price_text = (
            f"{currency} {price}"
            .strip()
        )

    availability = (
        product.get(
            "available_for_sale"
        )
    )

    if availability is True:
        availability_text = (
            "available hai"
            if response_language
            == "roman_urdu"
            else "is available"
        )
    elif availability is False:
        availability_text = (
            "currently available nahi hai"
            if response_language
            == "roman_urdu"
            else "is currently unavailable"
        )
    else:
        availability_text = (
            "availability confirm nahi hai"
            if response_language
            == "roman_urdu"
            else "has unknown availability"
        )

    return localized_message(
        response_language,
        (
            f"{title} costs {price_text} and "
            f"{availability_text}."
        ),
        (
            f"{title} ki price {price_text} hai aur "
            f"yeh {availability_text}."
        ),
    )


def _query_requests_cheaper_similar(
    query: str,
) -> bool:
    return bool(
        re.search(
            r"\\b(?:"
            r"cheaper|lower price|"
            r"sasta|sasti|saste|"
            r"kam price"
            r")\\b",
            query or "",
            flags=re.IGNORECASE,
        )
    )


def _deduplicate_types(
    values: list[str],
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean_value = " ".join(
            str(value or "")
            .strip()
            .split()
        )

        key = (
            clean_value.lower()
        )

        if (
            not clean_value
            or key in seen
        ):
            continue

        seen.add(key)
        unique.append(
            clean_value
        )

    return unique


def _clean_shop_domain(
    value: Any,
) -> str | None:
    clean_value = " ".join(
        str(value or "")
        .strip()
        .split()
    )

    if not clean_value:
        return None

    return clean_value[:255]


def _safe_clarification_filters(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Accept only the catalog refinement fields generated by the
    backend's clarification options.
    """
    if not isinstance(
        payload,
        dict,
    ):
        return {}

    allowed_keys = {
        "productType",
        "taxonomyCategory",
        "collection",
        "handle",
        "vendor",
        "minPrice",
        "maxPrice",
    }

    safe: dict[str, Any] = {}

    for key in allowed_keys:
        value = payload.get(key)

        if value is None:
            continue

        if key in {
            "minPrice",
            "maxPrice",
        }:
            try:
                safe[key] = float(
                    value
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            continue

        clean_value = " ".join(
            str(value)
            .strip()
            .split()
        )

        if clean_value:
            safe[key] = (
                clean_value[:300]
            )

    return safe


def add_price_explanations(
    products: list[dict],
    intent: str,
    response_language: str,
) -> list[dict]:
    for product in products:
        price = product.get(
            "price"
        )

        if (
            intent
            == "lowest_price"
        ):
            summary = (
                localized_message(
                    response_language,
                    (
                        "One of the lowest-priced "
                        "matching products."
                    ),
                    (
                        "Yeh matching products mein "
                        "kam price wala option hai."
                    ),
                )
            )

            ranking_reason = (
                localized_message(
                    response_language,
                    (
                        "Ranked from lower to "
                        "higher price."
                    ),
                    (
                        "Products ko kam se zyada "
                        "price mein rank kiya gaya hai."
                    ),
                )
            )
        else:
            summary = (
                localized_message(
                    response_language,
                    (
                        "One of the highest-priced "
                        "matching products."
                    ),
                    (
                        "Yeh matching products mein "
                        "zyada price wala option hai."
                    ),
                )
            )

            ranking_reason = (
                localized_message(
                    response_language,
                    (
                        "Ranked from higher to "
                        "lower price."
                    ),
                    (
                        "Products ko zyada se kam "
                        "price mein rank kiya gaya hai."
                    ),
                )
            )

        reasons = [
            (
                f"Price: ${price}."
                if price is not None
                else localized_message(
                    response_language,
                    (
                        "Price is unavailable."
                    ),
                    (
                        "Price available nahi hai."
                    ),
                )
            ),
            ranking_reason,
        ]

        if product.get(
            "vendor"
        ):
            reasons.append(
                (
                    "Vendor: "
                    f"{product['vendor']}."
                )
            )

        if product.get(
            "product_type"
        ):
            reasons.append(
                (
                    "Product type: "
                    f"{product['product_type']}."
                )
            )

        product["explanation"] = {
            "summary": summary,
            "reasons": reasons[:4],
        }

    return products


def _build_multi_category_response(
    requested_types: list[str],
    unresolved_types: list[str],
    base_filters: dict,
    limit: int,
    response_language: str,
    query_corrections: list[dict],
) -> dict:
    # A default limit of five would produce twenty products for
    # four categories. Keep the storefront response compact.
    per_category_limit = max(
        1,
        min(
            limit,
            3,
        ),
    )

    search_filters = dict(
        base_filters or {}
    )

    search_filters.pop(
        "productType",
        None,
    )
    search_filters.pop(
        "productTypes",
        None,
    )

    groups = (
        get_grouped_products_by_types(
            product_types=(
                requested_types
            ),
            base_filters=(
                search_filters
            ),
            per_type_limit=50,
        )
    )

    response_groups: list[
        dict
    ] = []

    flattened_products: list[
        dict
    ] = []

    available_types: list[
        str
    ] = []

    missing_types: list[
        str
    ] = list(
        unresolved_types
    )

    sort = search_filters.get(
        "sort"
    )

    for group in groups:
        product_type = group[
            "productType"
        ]
        products = group[
            "products"
        ]

        if not products:
            missing_types.append(
                product_type
            )
            continue

        if sort in {
            "price_low",
            "price_high",
        }:
            ranked = products[
                :per_category_limit
            ]

            ranking_mode = (
                "strict_price_sort"
            )
        else:
            category_embedding = (
                generate_text_embedding(
                    product_type
                )
            )

            ranked = (
                find_similar_products(
                    category_embedding,
                    products,
                    top_k=(
                        per_category_limit
                    ),
                    query_text=(
                        product_type
                    ),
                )
            )

            ranking_mode = (
                "strict_category_semantic"
            )

        available_types.append(
            product_type
        )

        public_ranked = (
            public_products(
                ranked
            )
        )

        for product in public_ranked:
            product[
                "requestedProductType"
            ] = product_type

            product["explanation"] = {
                "summary": (
                    localized_message(
                        response_language,
                        (
                            "Matches the requested "
                            f"{product_type} category."
                        ),
                        (
                            "Yeh requested "
                            f"{product_type} category "
                            "se match karta hai."
                        ),
                    )
                ),
                "reasons": [
                    localized_message(
                        response_language,
                        (
                            "Searched only inside the "
                            f"{product_type} category."
                        ),
                        (
                            "Search sirf "
                            f"{product_type} category "
                            "ke andar ki gayi hai."
                        ),
                    ),
                    localized_message(
                        response_language,
                        (
                            "Unrelated product categories "
                            "were excluded."
                        ),
                        (
                            "Unrelated product categories "
                            "exclude kar di gayi hain."
                        ),
                    ),
                ],
            }

        response_groups.append({
            "productType": (
                product_type
            ),
            "rankingMode": (
                ranking_mode
            ),
            "products": (
                public_ranked
            ),
        })

        flattened_products.extend(
            public_ranked
        )

    if available_types:
        found_text = ", ".join(
            available_types
        )

        if missing_types:
            missing_text = ", ".join(
                missing_types
            )

            message = (
                localized_message(
                    response_language,
                    (
                        "I found matching products for "
                        f"{found_text}. No catalog products "
                        f"were found for {missing_text}."
                    ),
                    (
                        f"{found_text} ke matching products "
                        "mil gaye hain. "
                        f"{missing_text} ke products catalog "
                        "mein nahi mile."
                    ),
                )
            )
        else:
            message = (
                localized_message(
                    response_language,
                    (
                        "I searched each requested "
                        "category separately."
                    ),
                    (
                        "Main ne har requested category "
                        "ko separately search kiya hai."
                    ),
                )
            )
    else:
        message = localized_message(
            response_language,
            (
                "No products were found in the "
                "requested categories."
            ),
            (
                "Requested categories mein koi "
                "product nahi mila."
            ),
        )

    return {
        "intent": (
            "multi_product_search"
        ),
        "responseLanguage": (
            response_language
        ),
        "requestedProductTypes": (
            requested_types
        ),
        "availableProductTypes": (
            available_types
        ),
        "missingProductTypes": (
            missing_types
        ),
        "filters": {
            **search_filters,
            "productTypes": (
                requested_types
            ),
        },
        "queryCorrections": (
            query_corrections
        ),
        "message": message,
        "productGroups": (
            response_groups
        ),
        "totalFilteredProducts": (
            len(
                flattened_products
            )
        ),
        "recommendedProducts": (
            flattened_products
        ),
    }


@router.get(
    "/suggestions"
)
def chat_suggestions(
    q: str = Query(
        ...,
        min_length=1,
    ),
):
    return {
        "success": True,
        "suggestions": (
            get_chat_suggestions(q)
        ),
    }


@router.post(
    "/search"
)
def shopping_chat(
    request: ChatRequest,
):
    original_query = (
        request.message.strip()
    )

    shop_domain = (
        _clean_shop_domain(
            request.shopDomain
        )
    )

    session_filters = (
        get_session(
            request.sessionId
        )
        or {}
    )

    conversation_state = (
        get_conversation_state(
            request.sessionId
        )
        or {}
    )

    last_products = (
        conversation_state.get(
            "last_products"
        )
        if isinstance(
            conversation_state.get(
                "last_products"
            ),
            list,
        )
        else []
    )

    selected_product = (
        conversation_state.get(
            "selected_product"
        )
        if isinstance(
            conversation_state.get(
                "selected_product"
            ),
            dict,
        )
        else None
    )

    vocabulary = (
        get_catalog_vocabulary(
            shop_domain=(
                shop_domain
            )
        )
    )

    structured_filters = (
        _safe_clarification_filters(
            request.clarificationFilters
        )
    )

    (
        normalized_query,
        query_corrections,
    ) = normalize_query_text(
        original_query,
        vocabulary,
    )

    result = parse_user_query(
        normalized_query,
        original_query=(
            original_query
        ),
        vocabulary=vocabulary,
    )

    response_language = (
        result.get(
            "responseLanguage",
            detect_response_language(
                original_query
            ),
        )
    )

    deterministic_language = (
        detect_response_language(
            original_query
        )
    )

    reference_selection_request = (
        detect_product_selection_request(
            original_query
        )
    )
    reference_detail_request = (
        detect_product_detail_request(
            original_query
        )
    )
    reference_similar_request = (
        detect_similar_product_request(
            original_query
        )
    )

    if (
        reference_selection_request
        or reference_detail_request
        or reference_similar_request
    ):
        response_language = (
            deterministic_language
        )

    intent = result.get(
        "intent",
        "out_of_context",
    )

    action = result.get(
        "action",
        "new_search",
    )

    limit = result.get(
        "limit",
        5,
    )

    mentioned_types = (
        detect_product_type_mentions(
            normalized_query,
            vocabulary,
        )
    )

    (
        parser_types,
        unresolved_parser_types,
        parser_type_corrections,
    ) = (
        resolve_requested_product_types(
            result.get(
                "productTypes",
                [],
            ),
            vocabulary,
        )
    )

    unresolved_types = (
        _deduplicate_types(
            unresolved_parser_types
            + result.get(
                "unresolvedProductTypes",
                [],
            )
        )
    )

    blocked_parser_types: list[str] = []

    if should_block_parser_only_catalog_types(
        explicit_mentions=mentioned_types,
        parser_types=parser_types,
        unresolved_types=unresolved_types,
    ):
        # The customer explicitly requested an unavailable product
        # term. Do not let a broad category inferred only by the LLM
        # unlock unrelated catalog products.
        blocked_parser_types = list(
            parser_types
        )
        parser_types = []

    requested_types = (
        _deduplicate_types(
            mentioned_types
            + parser_types
        )
    )

    structured_type_corrections: list[
        dict[str, str]
    ] = []

    structured_product_type = (
        structured_filters.get(
            "productType"
        )
    )

    if structured_product_type:
        (
            resolved_structured_types,
            _,
            structured_type_corrections,
        ) = resolve_requested_product_types(
            [structured_product_type],
            vocabulary,
        )

        if resolved_structured_types:
            structured_filters[
                "productType"
            ] = (
                resolved_structured_types[0]
            )

            requested_types = (
                _deduplicate_types(
                    resolved_structured_types
                    + requested_types
                )
            )
        else:
            structured_filters.pop(
                "productType",
                None,
            )

    if request.clarificationAction in {
        "apply_catalog_facet",
        "show_all_product_type",
    }:
        # The option came from a previously validated backend
        # clarification response. Facet words must not be reclassified
        # as unknown product types by the LLM.
        unresolved_types = []

    type_request_mode = (
        classify_product_type_request(
            normalized_query,
            requested_types,
            parser_relation=(
                result.get(
                    "relation"
                )
            ),
        )
    )

    # Product mentions take precedence over an occasional
    # out-of-context parser result.
    if (
        requested_types
        and intent
        == "out_of_context"
    ):
        intent = (
            "multi_product_search"
            if type_request_mode
            == "multi_list"
            else "product_search"
        )

    if (
        type_request_mode
        == "multi_list"
        and len(
            requested_types
        ) >= 2
        and intent
        != "compare_products"
    ):
        intent = (
            "multi_product_search"
        )

    print(
        "\n========== PARSER RESULT =========="
    )
    print(result)
    print(
        "Normalized query:",
        normalized_query,
    )
    print(
        "Requested types:",
        requested_types,
    )
    print(
        "Unresolved types:",
        unresolved_types,
    )
    print(
        "Blocked parser-only types:",
        blocked_parser_types,
    )
    print(
        "Type request mode:",
        type_request_mode,
    )
    print(
        "Corrections:",
        query_corrections,
    )
    print(
        "===================================\n"
    )

    if (
        intent == "greeting"
        and not (
            reference_selection_request
            or reference_detail_request
            or reference_similar_request
        )
    ):
        return {
            "intent": "greeting",
            "responseLanguage": (
                response_language
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "👋 Hello! I'm your AI "
                        "Shopping Assistant. Tell "
                        "me what product you're "
                        "looking for."
                    ),
                    (
                        "👋 Salam! Main aapka AI "
                        "Shopping Assistant hoon. "
                        "Batayein aap kya dhoond "
                        "rahe hain."
                    ),
                )
            ),
            "recommendedProducts": [],
        }

    if intent == "reset":
        delete_session(
            request.sessionId
        )

        return {
            "intent": "reset",
            "responseLanguage": (
                response_language
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "Your shopping session "
                        "has been reset."
                    ),
                    (
                        "Aapki shopping session "
                        "reset ho gayi hai."
                    ),
                )
            ),
            "recommendedProducts": [],
        }

    if reference_selection_request:
        reference_result = (
            resolve_product_references(
                original_query,
                last_products,
                selected_product,
            )
        )

        resolved = (
            reference_result[
                "resolved"
            ]
        )

        if len(resolved) != 1:
            return (
                _reference_clarification(
                    response_language=(
                        response_language
                    ),
                    last_products=(
                        last_products
                    ),
                    unresolved=(
                        reference_result[
                            "unresolved"
                        ]
                    ),
                )
            )

        selected = resolved[0]

        updated_state = select_product(
            conversation_state,
            selected,
        )

        save_conversation_state(
            request.sessionId,
            updated_state,
            filters=(
                session_filters
            ),
            last_query=(
                original_query
            ),
        )

        return {
            "intent": (
                "select_product"
            ),
            "responseLanguage": (
                response_language
            ),
            "selectedProduct": (
                selected
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        f"{selected.get('title') or 'The product'} "
                        "is now selected for follow-up questions."
                    ),
                    (
                        f"{selected.get('title') or 'Product'} "
                        "select kar liya gaya hai. Ab is ke "
                        "baray mein follow-up pooch sakte hain."
                    ),
                )
            ),
            "recommendedProducts": [
                selected
            ],
        }

    if reference_detail_request:
        reference_result = (
            resolve_product_references(
                original_query,
                last_products,
                selected_product,
            )
        )

        resolved = (
            reference_result[
                "resolved"
            ]
        )

        if len(resolved) != 1:
            return (
                _reference_clarification(
                    response_language=(
                        response_language
                    ),
                    last_products=(
                        last_products
                    ),
                    unresolved=(
                        reference_result[
                            "unresolved"
                        ]
                    ),
                )
            )

        selected = resolved[0]

        updated_state = select_product(
            conversation_state,
            selected,
        )

        save_conversation_state(
            request.sessionId,
            updated_state,
            filters=(
                session_filters
            ),
            last_query=(
                original_query
            ),
        )

        return {
            "intent": (
                "product_detail_followup"
            ),
            "responseLanguage": (
                response_language
            ),
            "selectedProduct": (
                selected
            ),
            "message": (
                _product_detail_message(
                    selected,
                    response_language,
                )
            ),
            "recommendedProducts": [
                selected
            ],
        }

    if reference_similar_request:
        reference_result = (
            resolve_product_references(
                original_query,
                last_products,
                selected_product,
            )
        )

        resolved = (
            reference_result[
                "resolved"
            ]
        )

        if len(resolved) != 1:
            return (
                _reference_clarification(
                    response_language=(
                        response_language
                    ),
                    last_products=(
                        last_products
                    ),
                    unresolved=(
                        reference_result[
                            "unresolved"
                        ]
                    ),
                )
            )

        catalog_products = (
            get_all_shopify_products(
                shop_domain=(
                    shop_domain
                )
            )
        )

        hydrated_reference = (
            hydrate_memory_products(
                resolved,
                catalog_products,
            )
        )[0]

        recommendations = (
            find_more_like_shopify_product(
                reference_product=(
                    hydrated_reference
                ),
                products=(
                    catalog_products
                ),
                top_k=limit,
                cheaper_only=(
                    _query_requests_cheaper_similar(
                        original_query
                    )
                ),
            )
        )

        if not recommendations:
            return {
                "intent": (
                    "clarification"
                ),
                "clarificationType": (
                    "similar_products_not_found"
                ),
                "responseLanguage": (
                    response_language
                ),
                "referenceProduct": (
                    resolved[0]
                ),
                "message": (
                    localized_message(
                        response_language,
                        (
                            "I could not find another sufficiently "
                            "similar catalog product."
                        ),
                        (
                            "Is product jaisa koi aur suitable "
                            "catalog product nahi mila."
                        ),
                    )
                ),
                "recommendedProducts": [],
            }

        explanation_query = (
            original_query
        )

        explanations = (
            generate_explanations(
                explanation_query,
                recommendations,
                response_language=(
                    response_language
                ),
            )
        )

        for product, explanation in zip(
            recommendations,
            explanations,
        ):
            product[
                "explanation"
            ] = explanation

        memory_filters = dict(
            session_filters
        )

        if shop_domain:
            memory_filters[
                "shopDomain"
            ] = shop_domain

        _remember_products(
            session_id=(
                request.sessionId
            ),
            products=(
                recommendations
            ),
            query=(
                original_query
            ),
            intent=(
                "similar_products"
            ),
            filters=(
                memory_filters
            ),
        )

        return {
            "intent": (
                "similar_products"
            ),
            "responseLanguage": (
                response_language
            ),
            "referenceProduct": (
                resolved[0]
            ),
            "rankingMode": (
                "conversation_more_like_this"
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "Here are products similar to "
                        f"{resolved[0].get('title') or 'the selected product'}."
                    ),
                    (
                        "Yeh products "
                        f"{resolved[0].get('title') or 'selected product'} "
                        "jaisay hain."
                    ),
                )
            ),
            "recommendedProducts": (
                public_products(
                    recommendations
                )
            ),
        }

    if intent == "compare_products":
        reference_result = (
            resolve_product_references(
                original_query,
                last_products,
                selected_product,
            )
        )

        catalog_products = (
            get_all_shopify_products(
                shop_domain=(
                    shop_domain
                )
            )
        )

        memory_matched = (
            hydrate_memory_products(
                reference_result[
                    "resolved"
                ],
                catalog_products,
            )
        )

        targets = result.get(
            "comparisonTargets",
            [],
        )

        if (
            len(memory_matched)
            >= 2
        ):
            matched = (
                memory_matched[:4]
            )
            unmatched = []
            targets = [
                (
                    product.get(
                        "title"
                    )
                    or (
                        "Product "
                        f"{index + 1}"
                    )
                )
                for index, product
                in enumerate(
                    matched
                )
            ]
        else:
            if len(targets) < 2:
                targets = (
                    extract_comparison_targets(
                        normalized_query
                    )
                )

            if len(targets) < 2:
                response = (
                    _reference_clarification(
                        response_language=(
                            response_language
                        ),
                        last_products=(
                            last_products
                        ),
                        unresolved=(
                            reference_result[
                                "unresolved"
                            ]
                        ),
                    )
                )

                response[
                    "clarificationType"
                ] = (
                    "comparison_targets_required"
                )

                return response

            match_result = (
                match_comparison_products(
                    targets=targets,
                    products=(
                        catalog_products
                    ),
                )
            )

            matched = match_result[
                "matched"
            ]
            unmatched = match_result[
                "unmatched"
            ]

        if len(matched) < 2:
            return {
                "intent": (
                    "clarification"
                ),
                "clarificationType": (
                    "comparison_products_not_found"
                ),
                "responseLanguage": (
                    response_language
                ),
                "message": (
                    localized_message(
                        response_language,
                        (
                            "I could not confidently "
                            "identify two catalog "
                            "products. Please select "
                            "from the suggested titles."
                        ),
                        (
                            "Main do catalog products "
                            "ko confidence ke saath "
                            "identify nahi kar saka. "
                            "Suggested titles mein se "
                            "select karein."
                        ),
                    )
                ),
                "comparisonTargets": (
                    targets
                ),
                "matchedProducts": (
                    public_products(
                        matched
                    )
                ),
                "unmatchedTargets": (
                    unmatched
                ),
                "recommendedProducts": [],
            }

        comparison = (
            build_product_comparison(
                matched
            )
        )

        comparison_summary = (
            generate_comparison_summary(
                user_query=(
                    original_query
                ),
                comparison=(
                    comparison
                ),
                response_language=(
                    response_language
                ),
            )
        )

        comparison[
            "aiSummary"
        ] = comparison_summary

        _remember_products(
            session_id=(
                request.sessionId
            ),
            products=(
                matched
            ),
            query=(
                original_query
            ),
            intent=(
                "compare_products"
            ),
            filters=(
                session_filters
            ),
        )

        return {
            "intent": (
                "compare_products"
            ),
            "responseLanguage": (
                response_language
            ),
            "comparisonTargets": (
                targets
            ),
            "comparison": comparison,
            "message": (
                comparison_summary[
                    "summary"
                ]
            ),
            "recommendedProducts": (
                comparison[
                    "products"
                ]
            ),
        }

    if (
        len(requested_types) > 1
        and type_request_mode
        in {
            "ambiguous",
            "complementary",
        }
    ):
        response = (
            build_multiple_type_clarification(
                product_types=(
                    requested_types
                ),
                response_language=(
                    response_language
                ),
            )
        )

        response[
            "responseLanguage"
        ] = response_language

        response[
            "queryCorrections"
        ] = (
            query_corrections
            + parser_type_corrections
        )

        return response

    if (
        unresolved_types
        and not requested_types
    ):
        response = (
            build_unknown_type_clarification(
                unresolved_types=(
                    unresolved_types
                ),
                suggestions=(
                    suggest_catalog_types(
                        unresolved_types,
                        vocabulary,
                    )
                ),
                response_language=(
                    response_language
                ),
            )
        )

        response[
            "responseLanguage"
        ] = response_language
        response[
            "queryCorrections"
        ] = query_corrections

        return response

    if (
        intent == "out_of_context"
        and not requested_types
        and not unresolved_types
    ):
        return {
            "intent": (
                "out_of_context"
            ),
            "responseLanguage": (
                response_language
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "Sorry, I can only help "
                        "with shopping and product "
                        "recommendations."
                    ),
                    (
                        "Maazrat, main sirf shopping "
                        "aur product recommendations "
                        "mein madad kar sakta hoon."
                    ),
                )
            ),
            "recommendedProducts": [],
        }

    current_filters = (
        normalize_filters(
            result.get(
                "filters",
                {},
            )
        )
    )

    (
        current_filters,
        filter_corrections,
    ) = normalize_filter_values(
        current_filters,
        vocabulary,
    )

    current_filters.update(
        structured_filters
    )

    if shop_domain:
        current_filters[
            "shopDomain"
        ] = shop_domain

    if request.clarificationAction in {
        "apply_catalog_facet",
        "show_all_product_type",
    }:
        action = "new_search"

    filter_type = (
        current_filters.get(
            "productType"
        )
    )

    if filter_type:
        (
            resolved_filter_types,
            unresolved_filter_types,
            filter_type_corrections,
        ) = (
            resolve_requested_product_types(
                [filter_type],
                vocabulary,
            )
        )

        filter_corrections.extend(
            filter_type_corrections
        )

        if resolved_filter_types:
            current_filters[
                "productType"
            ] = resolved_filter_types[0]

        elif unresolved_filter_types:
            response = (
                build_unknown_type_clarification(
                    unresolved_types=(
                        unresolved_filter_types
                    ),
                    suggestions=(
                        suggest_catalog_types(
                            unresolved_filter_types,
                            vocabulary,
                        )
                    ),
                    response_language=(
                        response_language
                    ),
                )
            )
            response[
                "responseLanguage"
            ] = response_language
            return response

    all_corrections = (
        query_corrections
        + parser_type_corrections
        + filter_corrections
        + structured_type_corrections
    )

    # Strict single-category guard:
    # if the user explicitly said "shirt", force the database
    # filter even when the LLM forgot to set productType.
    if (
        len(requested_types) == 1
        and not current_filters.get(
            "productType"
        )
    ):
        current_filters[
            "productType"
        ] = requested_types[0]

    previous_filters = (
        session_filters
    )

    if action == "modify":
        merged_filters = (
            merge_filters(
                previous_filters,
                current_filters,
            )
        )
    else:
        merged_filters = (
            current_filters
        )

    if intent == "lowest_price":
        merged_filters[
            "sort"
        ] = "price_low"

    elif intent == "highest_price":
        merged_filters[
            "sort"
        ] = "price_high"

    if (
        intent
        == "multi_product_search"
    ):
        merged_filters.pop(
            "productType",
            None,
        )
        merged_filters[
            "productTypes"
        ] = requested_types

    if shop_domain:
        merged_filters[
            "shopDomain"
        ] = shop_domain

    if (
        intent
        in {
            "product_search",
            "recommend_products",
        }
        and merged_filters.get(
            "productType"
        )
        and not merged_filters.get(
            "productTypes"
        )
    ):
        broad_product_type = (
            merged_filters[
                "productType"
            ]
        )

        category_profile = (
            get_product_type_profile(
                product_type=(
                    broad_product_type
                ),
                shop_domain=(
                    shop_domain
                ),
            )
        )

        dynamic_facets = (
            prepare_catalog_facets(
                category_profile
            )
        )

        selected_facet = None

        if (
            not merged_filters.get(
                "taxonomyCategory"
            )
            and not merged_filters.get(
                "collection"
            )
            and request.clarificationAction
            not in {
                "apply_catalog_facet",
                "show_all_product_type",
            }
        ):
            selected_facet = (
                match_query_to_catalog_facet(
                    query=(
                        original_query
                    ),
                    product_type=(
                        broad_product_type
                    ),
                    facets=(
                        dynamic_facets
                    ),
                )
            )

        if selected_facet:
            if (
                selected_facet.get(
                    "type"
                )
                == "taxonomy"
            ):
                merged_filters[
                    "taxonomyCategory"
                ] = selected_facet.get(
                    "value"
                )

            elif (
                selected_facet.get(
                    "type"
                )
                == "collection"
            ):
                merged_filters[
                    "collection"
                ] = selected_facet.get(
                    "value"
                )

            elif (
                selected_facet.get(
                    "type"
                )
                == "product"
            ):
                merged_filters[
                    "handle"
                ] = selected_facet.get(
                    "value"
                )

        should_ask_category = (
            should_clarify_broad_category(
                product_type=(
                    broad_product_type
                ),
                profile=(
                    category_profile
                ),
                active_filters=(
                    merged_filters
                ),
                original_query=(
                    original_query
                ),
                bypass=(
                    request
                    .bypassBroadCategoryClarification
                    or request
                    .clarificationAction
                    == "show_all_product_type"
                ),
            )
        )

        print(
            "Broad category profile:",
            {
                "productType": (
                    broad_product_type
                ),
                "productCount": (
                    category_profile.get(
                        "productCount",
                        0,
                    )
                ),
                "titleMatchRatio": (
                    category_profile.get(
                        "titleMatchRatio",
                        0.0,
                    )
                ),
                "taxonomyFacets": (
                    category_profile.get(
                        "taxonomyFacetCount",
                        0,
                    )
                ),
                "collectionFacets": (
                    category_profile.get(
                        "collectionFacetCount",
                        0,
                    )
                ),
                "productFacets": (
                    category_profile.get(
                        "productFacetCount",
                        0,
                    )
                ),
                "fallbackMode": (
                    category_profile.get(
                        "fallbackFacetMode"
                    )
                ),
                "shouldClarify": (
                    should_ask_category
                ),
            },
        )

        if should_ask_category:
            save_session(
                request.sessionId,
                merged_filters,
                original_query,
            )

            response = (
                build_broad_category_clarification(
                    product_type=(
                        broad_product_type
                    ),
                    facets=(
                        dynamic_facets
                    ),
                    response_language=(
                        response_language
                    ),
                    product_count=int(
                        category_profile.get(
                            "productCount"
                        )
                        or 0
                    ),
                )
            )

            response[
                "filters"
            ] = merged_filters

            response[
                "queryCorrections"
            ] = all_corrections

            response[
                "catalogProfile"
            ] = {
                "productCount": (
                    category_profile.get(
                        "productCount",
                        0,
                    )
                ),
                "titleMatchRatio": (
                    category_profile.get(
                        "titleMatchRatio",
                        0.0,
                    )
                ),
                "taxonomyFacetCount": (
                    category_profile.get(
                        "taxonomyFacetCount",
                        0,
                    )
                ),
                "collectionFacetCount": (
                    category_profile.get(
                        "collectionFacetCount",
                        0,
                    )
                ),
                "productFacetCount": (
                    category_profile.get(
                        "productFacetCount",
                        0,
                    )
                ),
                "fallbackFacetMode": (
                    category_profile.get(
                        "fallbackFacetMode"
                    )
                ),
            }

            return response

    save_session(
        request.sessionId,
        merged_filters,
        original_query,
    )

    if (
        intent
        == "multi_product_search"
    ):
        response = (
            _build_multi_category_response(
                requested_types=(
                    requested_types
                ),
                unresolved_types=(
                    unresolved_types
                ),
                base_filters=(
                    merged_filters
                ),
                limit=limit,
                response_language=(
                    response_language
                ),
                query_corrections=(
                    all_corrections
                ),
            )
        )

        _remember_products(
            session_id=(
                request.sessionId
            ),
            products=(
                response.get(
                    "recommendedProducts",
                    [],
                )
            ),
            query=(
                original_query
            ),
            intent=(
                "multi_product_search"
            ),
            filters=(
                merged_filters
            ),
        )

        return response

    if intent == "newest_products":
        newest_filters = dict(
            merged_filters
        )
        newest_filters[
            "sort"
        ] = "newest"

        products = (
            get_filtered_products(
                newest_filters,
                limit=limit,
            )
        )

        _remember_products(
            session_id=(
                request.sessionId
            ),
            products=(
                products
            ),
            query=(
                original_query
            ),
            intent=(
                "newest_products"
            ),
            filters=(
                newest_filters
            ),
        )

        return {
            "intent": (
                "newest_products"
            ),
            "responseLanguage": (
                response_language
            ),
            "filters": (
                newest_filters
            ),
            "queryCorrections": (
                all_corrections
            ),
            "rankingMode": (
                "shopify_created_at"
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "Here are the newest "
                        "matching products."
                    ),
                    (
                        "Yeh sab se naye "
                        "matching products hain."
                    ),
                )
            ),
            "totalFilteredProducts": (
                len(products)
            ),
            "recommendedProducts": (
                public_products(
                    products
                )
            ),
        }

    if intent == "top_products":
        products = (
            get_filtered_products(
                merged_filters,
                limit=limit,
            )
        )

        _remember_products(
            session_id=(
                request.sessionId
            ),
            products=(
                products
            ),
            query=(
                original_query
            ),
            intent=(
                "top_products"
            ),
            filters=(
                merged_filters
            ),
        )

        return {
            "intent": (
                "top_products"
            ),
            "responseLanguage": (
                response_language
            ),
            "queryCorrections": (
                all_corrections
            ),
            "rankingMode": (
                "temporary_catalog_fallback"
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "Top-products intent was "
                        "detected. Real popularity "
                        "ranking needs sales, click, "
                        "rating, or add-to-cart data."
                    ),
                    (
                        "Top-products intent detect "
                        "ho gaya hai. Real popularity "
                        "ranking ke liye sales, clicks, "
                        "ratings ya add-to-cart data "
                        "chahiye."
                    ),
                )
            ),
            "totalFilteredProducts": (
                len(products)
            ),
            "recommendedProducts": (
                public_products(
                    products
                )
            ),
        }

    database_limit = (
        limit
        if intent in {
            "lowest_price",
            "highest_price",
        }
        else 200
    )

    products = (
        get_filtered_products(
            merged_filters,
            limit=database_limit,
        )
    )

    if not products:
        response = (
            build_no_result_clarification(
                filters=(
                    merged_filters
                ),
                response_language=(
                    response_language
                ),
                search_function=(
                    get_filtered_products
                ),
            )
        )

        response[
            "responseLanguage"
        ] = response_language

        response[
            "filters"
        ] = merged_filters

        response[
            "queryCorrections"
        ] = all_corrections

        return response

    if intent in {
        "lowest_price",
        "highest_price",
    }:
        recommendations = (
            add_price_explanations(
                products=(
                    products[:limit]
                ),
                intent=intent,
                response_language=(
                    response_language
                ),
            )
        )

        _remember_products(
            session_id=(
                request.sessionId
            ),
            products=(
                recommendations
            ),
            query=(
                original_query
            ),
            intent=(
                intent
            ),
            filters=(
                merged_filters
            ),
        )

        return {
            "intent": intent,
            "responseLanguage": (
                response_language
            ),
            "action": action,
            "filters": (
                merged_filters
            ),
            "queryCorrections": (
                all_corrections
            ),
            "sort": (
                merged_filters.get(
                    "sort"
                )
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        f"Here are "
                        f"{len(recommendations)} "
                        "price-sorted matching "
                        "products."
                    ),
                    (
                        f"Yeh "
                        f"{len(recommendations)} "
                        "matching products price "
                        "ke mutabiq sorted hain."
                    ),
                )
            ),
            "totalFilteredProducts": (
                len(products)
            ),
            "recommendedProducts": (
                public_products(
                    recommendations
                )
            ),
        }

    semantic_query = (
        result.get(
            "semanticQuery"
        )
        or normalized_query
    )

    embedding = (
        generate_text_embedding(
            semantic_query
        )
    )

    recommendations = (
        find_similar_products(
            embedding,
            products,
            top_k=limit,
            query_text=(
                semantic_query
            ),
        )
    )

    if (
        semantic_result_is_low_confidence(
            recommendations
        )
    ):
        response = (
            build_low_confidence_clarification(
                filters=(
                    merged_filters
                ),
                response_language=(
                    response_language
                ),
                search_function=(
                    get_filtered_products
                ),
            )
        )

        response[
            "responseLanguage"
        ] = response_language

        response[
            "filters"
        ] = merged_filters

        response[
            "queryCorrections"
        ] = all_corrections

        return response

    explanations = (
        generate_explanations(
            original_query,
            recommendations,
            response_language=(
                response_language
            ),
        )
    )

    for (
        product,
        explanation,
    ) in zip(
        recommendations,
        explanations,
    ):
        product[
            "explanation"
        ] = explanation

    _remember_products(
        session_id=(
            request.sessionId
        ),
        products=(
            recommendations
        ),
        query=(
            original_query
        ),
        intent=(
            intent
        ),
        filters=(
            merged_filters
        ),
    )

    return {
        "intent": intent,
        "responseLanguage": (
            response_language
        ),
        "action": action,
        "filters": (
            merged_filters
        ),
        "queryCorrections": (
            all_corrections
        ),
        "normalizedQuery": (
            normalized_query
        ),
        "semanticQuery": (
            semantic_query
        ),
        "parserStatus": (
            result.get(
                "parserStatus"
            )
        ),
        "message": (
            localized_message(
                response_language,
                (
                    "Here are the matching "
                    "products."
                ),
                (
                    "Yeh aapki search se "
                    "matching products hain."
                ),
            )
        ),
        "totalFilteredProducts": (
            len(products)
        ),
        "recommendedProducts": (
            public_products(
                recommendations
            )
        ),
    }
