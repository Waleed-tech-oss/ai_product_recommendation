from fastapi import (
    APIRouter,
    Query,
)
from pydantic import BaseModel

from database.postgres import (
    get_all_shopify_products,
    get_catalog_vocabulary,
    get_chat_suggestions,
    get_filtered_products,
    get_grouped_products_by_types,
)
from database.chat_session import (
    delete_session,
    get_session,
    save_session,
)

from services.chat_service import (
    parse_user_query,
)
from services.clarification_service import (
    build_low_confidence_clarification,
    build_multiple_type_clarification,
    build_no_result_clarification,
    semantic_result_is_low_confidence,
)
from services.clip_service import (
    generate_text_embedding,
)
from services.comparison_service import (
    build_product_comparison,
    extract_comparison_targets,
    match_comparison_products,
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
    normalize_requested_product_types,
)
from services.recommendation_service import (
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
            if key != "embedding"
        }
        for product in products
    ]


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
    ] = []

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

    vocabulary = (
        get_catalog_vocabulary()
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
    )

    response_language = (
        result.get(
            "responseLanguage",
            detect_response_language(
                original_query
            ),
        )
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
        parser_type_corrections,
    ) = (
        normalize_requested_product_types(
            result.get(
                "productTypes",
                [],
            ),
            vocabulary,
        )
    )

    requested_types = (
        _deduplicate_types(
            mentioned_types
            + parser_types
        )
    )

    type_request_mode = (
        classify_product_type_request(
            normalized_query,
            requested_types,
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

    if intent == "greeting":
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

    if intent == "compare_products":
        targets = result.get(
            "comparisonTargets",
            [],
        )

        if len(targets) < 2:
            targets = (
                extract_comparison_targets(
                    normalized_query
                )
            )

        if len(targets) < 2:
            return {
                "intent": (
                    "clarification"
                ),
                "clarificationType": (
                    "comparison_targets_required"
                ),
                "responseLanguage": (
                    response_language
                ),
                "message": (
                    localized_message(
                        response_language,
                        (
                            "Please tell me the "
                            "names of at least two "
                            "products to compare."
                        ),
                        (
                            "Compare karne ke liye "
                            "kam az kam do products "
                            "ke naam batayein."
                        ),
                    )
                ),
                "options": [],
                "recommendedProducts": [],
            }

        catalog_products = (
            get_all_shopify_products()
        )

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
        == "ambiguous"
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
        intent == "out_of_context"
        and not requested_types
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

    all_corrections = (
        query_corrections
        + parser_type_corrections
        + filter_corrections
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
        get_session(
            request.sessionId
        )
        or {}
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

    save_session(
        request.sessionId,
        merged_filters,
        original_query,
    )

    if (
        intent
        == "multi_product_search"
    ):
        return (
            _build_multi_category_response(
                requested_types=(
                    requested_types
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

    if intent == "newest_products":
        return {
            "intent": (
                "newest_products"
            ),
            "responseLanguage": (
                response_language
            ),
            "queryCorrections": (
                all_corrections
            ),
            "message": (
                localized_message(
                    response_language,
                    (
                        "Newest-products intent "
                        "was detected, but Shopify "
                        "createdAt is not stored yet."
                    ),
                    (
                        "Newest-products intent "
                        "detect ho gaya hai, lekin "
                        "Shopify createdAt abhi "
                        "database mein store nahi "
                        "ho raha."
                    ),
                )
            ),
            "recommendedProducts": [],
        }

    if intent == "top_products":
        products = (
            get_filtered_products(
                merged_filters,
                limit=limit,
            )
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
