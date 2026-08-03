from fastapi import APIRouter, Query
from pydantic import BaseModel

from database.postgres import (
    get_all_shopify_products,
    get_catalog_vocabulary,
    get_chat_suggestions,
    get_filtered_products,
)
from database.chat_session import (
    delete_session,
    get_session,
    save_session,
)

from services.chat_service import parse_user_query
from services.clarification_service import (
    build_low_confidence_clarification,
    build_multiple_type_clarification,
    build_no_result_clarification,
    semantic_result_is_low_confidence,
)
from services.clip_service import generate_text_embedding
from services.comparison_service import (
    build_product_comparison,
    extract_comparison_targets,
    match_comparison_products,
)
from services.filter_merger import merge_filters
from services.filter_normalizer import normalize_filters
from services.groq_service import (
    generate_comparison_summary,
    generate_explanations,
)
from services.intent_service import (
    detect_response_language,
)
from services.query_normalizer import (
    detect_product_type_mentions,
    normalize_filter_values,
    normalize_query_text,
)
from services.recommendation_service import (
    find_similar_products,
)


router = APIRouter(
    prefix="/chat",
    tags=["Shopping Assistant"],
)


class ChatRequest(BaseModel):
    sessionId: str
    message: str


def localized_message(
    response_language: str,
    english: str,
    roman_urdu: str,
) -> str:
    return (
        roman_urdu
        if response_language == "roman_urdu"
        else english
    )


def public_products(
    products: list[dict],
) -> list[dict]:
    return [
        {
            key: value
            for key, value in product.items()
            if key != "embedding"
        }
        for product in products
    ]


def add_price_explanations(
    products: list[dict],
    intent: str,
    response_language: str,
) -> list[dict]:
    for product in products:
        price = product.get("price")

        if intent == "lowest_price":
            summary = localized_message(
                response_language,
                "One of the lowest-priced matching products.",
                "Yeh matching products mein kam price wala option hai.",
            )
            ranking_reason = localized_message(
                response_language,
                "Ranked from lower to higher price.",
                "Products ko kam se zyada price mein rank kiya gaya hai.",
            )
        else:
            summary = localized_message(
                response_language,
                "One of the highest-priced matching products.",
                "Yeh matching products mein zyada price wala option hai.",
            )
            ranking_reason = localized_message(
                response_language,
                "Ranked from higher to lower price.",
                "Products ko zyada se kam price mein rank kiya gaya hai.",
            )

        reasons = [
            (
                f"Price: ${price}."
                if price is not None
                else localized_message(
                    response_language,
                    "Price is unavailable.",
                    "Price available nahi hai.",
                )
            ),
            ranking_reason,
        ]

        if product.get("vendor"):
            reasons.append(
                f"Vendor: {product['vendor']}."
            )

        if product.get("product_type"):
            reasons.append(
                f"Product type: {product['product_type']}."
            )

        while len(reasons) < 4:
            reasons.append(
                localized_message(
                    response_language,
                    "Matches the available shopping filters.",
                    "Available shopping filters se match karta hai.",
                )
            )

        product["explanation"] = {
            "summary": summary,
            "reasons": reasons[:4],
        }

    return products


@router.get("/suggestions")
def chat_suggestions(
    q: str = Query(..., min_length=1),
):
    return {
        "success": True,
        "suggestions": get_chat_suggestions(q),
    }


@router.post("/search")
def shopping_chat(request: ChatRequest):
    original_query = request.message.strip()

    # ------------------------------------
    # Step 1: Catalog vocabulary
    # ------------------------------------

    vocabulary = get_catalog_vocabulary()

    # ------------------------------------
    # Step 2: Synonym + typo correction
    # ------------------------------------

    normalized_query, query_corrections = (
        normalize_query_text(
            original_query,
            vocabulary,
        )
    )

    # ------------------------------------
    # Step 3: Parse intent and filters
    # ------------------------------------

    result = parse_user_query(
        normalized_query,
        original_query=original_query,
    )

    response_language = result.get(
        "responseLanguage",
        detect_response_language(
            original_query
        ),
    )

    intent = result["intent"]
    action = result.get(
        "action",
        "new_search",
    )
    limit = result.get("limit", 5)

    print("\n========== PARSER RESULT ==========")
    print(result)
    print("Normalized query:", normalized_query)
    print("Corrections:", query_corrections)
    print("===================================\n")

    if intent == "greeting":
        return {
            "intent": "greeting",
            "responseLanguage": response_language,
            "message": localized_message(
                response_language,
                (
                    "👋 Hello! I'm your AI Shopping Assistant. "
                    "Tell me what product you're looking for."
                ),
                (
                    "👋 Salam! Main aapka AI Shopping Assistant hoon. "
                    "Batayein aap kya dhoond rahe hain."
                ),
            ),
            "recommendedProducts": [],
        }

    if intent == "reset":
        delete_session(request.sessionId)

        return {
            "intent": "reset",
            "responseLanguage": response_language,
            "message": localized_message(
                response_language,
                "Your shopping session has been reset.",
                "Aapki shopping session reset ho gayi hai.",
            ),
            "recommendedProducts": [],
        }

    if intent == "out_of_context":
        return {
            "intent": "out_of_context",
            "responseLanguage": response_language,
            "message": localized_message(
                response_language,
                (
                    "Sorry, I can only help with shopping "
                    "and product recommendations."
                ),
                (
                    "Maazrat, main sirf shopping aur product "
                    "recommendations mein madad kar sakta hoon."
                ),
            ),
            "recommendedProducts": [],
        }

    # ------------------------------------
    # Step 4: Proper product comparison
    # ------------------------------------

    if intent == "compare_products":
        targets = result.get(
            "comparisonTargets",
            [],
        )

        if len(targets) < 2:
            targets = extract_comparison_targets(
                normalized_query
            )

        if len(targets) < 2:
            return {
                "intent": "clarification",
                "clarificationType": (
                    "comparison_targets_required"
                ),
                "responseLanguage": response_language,
                "message": localized_message(
                    response_language,
                    (
                        "Please tell me the names of at least "
                        "two products to compare."
                    ),
                    (
                        "Compare karne ke liye kam az kam "
                        "do products ke naam batayein."
                    ),
                ),
                "options": [],
                "recommendedProducts": [],
            }

        catalog_products = (
            get_all_shopify_products()
        )

        match_result = match_comparison_products(
            targets=targets,
            products=catalog_products,
        )

        matched = match_result["matched"]
        unmatched = match_result["unmatched"]

        if len(matched) < 2:
            return {
                "intent": "clarification",
                "clarificationType": (
                    "comparison_products_not_found"
                ),
                "responseLanguage": response_language,
                "message": localized_message(
                    response_language,
                    (
                        "I could not confidently identify two "
                        "catalog products. Please select from "
                        "the suggested titles."
                    ),
                    (
                        "Main do catalog products ko confidence "
                        "ke saath identify nahi kar saka. "
                        "Suggested titles mein se select karein."
                    ),
                ),
                "comparisonTargets": targets,
                "matchedProducts": public_products(
                    matched
                ),
                "unmatchedTargets": unmatched,
                "recommendedProducts": [],
            }

        comparison = build_product_comparison(
            matched
        )

        comparison_summary = (
            generate_comparison_summary(
                user_query=original_query,
                comparison=comparison,
                response_language=(
                    response_language
                ),
            )
        )

        comparison["aiSummary"] = (
            comparison_summary
        )

        return {
            "intent": "compare_products",
            "responseLanguage": response_language,
            "comparisonTargets": targets,
            "comparison": comparison,
            "message": comparison_summary[
                "summary"
            ],
            "recommendedProducts": (
                comparison["products"]
            ),
        }

    # ------------------------------------
    # Step 5: Detect impossible/ambiguous
    # product combinations
    # ------------------------------------

    mentioned_types = (
        detect_product_type_mentions(
            normalized_query,
            vocabulary,
        )
    )

    if len(mentioned_types) > 1:
        response = (
            build_multiple_type_clarification(
                product_types=mentioned_types,
                response_language=(
                    response_language
                ),
            )
        )

        response["responseLanguage"] = (
            response_language
        )
        response["queryCorrections"] = (
            query_corrections
        )

        return response

    # ------------------------------------
    # Step 6: Normalize filters and fix
    # catalog spelling
    # ------------------------------------

    current_filters = normalize_filters(
        result.get("filters", {})
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
        + filter_corrections
    )

    previous_filters = get_session(
        request.sessionId
    ) or {}

    if action == "modify":
        merged_filters = merge_filters(
            previous_filters,
            current_filters,
        )
    else:
        merged_filters = current_filters

    if intent == "lowest_price":
        merged_filters["sort"] = (
            "price_low"
        )

    elif intent == "highest_price":
        merged_filters["sort"] = (
            "price_high"
        )

    save_session(
        request.sessionId,
        merged_filters,
        original_query,
    )

    # ------------------------------------
    # Current schema cannot truly sort
    # by Shopify creation date yet.
    # ------------------------------------

    if intent == "newest_products":
        return {
            "intent": "newest_products",
            "responseLanguage": response_language,
            "queryCorrections": all_corrections,
            "message": localized_message(
                response_language,
                (
                    "Newest-products intent was detected, "
                    "but Shopify createdAt is not stored yet."
                ),
                (
                    "Newest-products intent detect ho gaya hai, "
                    "lekin Shopify createdAt abhi database mein "
                    "store nahi ho raha."
                ),
            ),
            "recommendedProducts": [],
        }

    # ------------------------------------
    # Temporary top-products fallback
    # ------------------------------------

    if intent == "top_products":
        products = get_filtered_products(
            merged_filters,
            limit=limit,
        )

        return {
            "intent": "top_products",
            "responseLanguage": response_language,
            "queryCorrections": all_corrections,
            "rankingMode": (
                "temporary_catalog_fallback"
            ),
            "message": localized_message(
                response_language,
                (
                    "Top-products intent was detected. "
                    "Real popularity ranking needs sales, "
                    "click, rating, or add-to-cart data."
                ),
                (
                    "Top-products intent detect ho gaya hai. "
                    "Real popularity ranking ke liye sales, "
                    "clicks, ratings ya add-to-cart data chahiye."
                ),
            ),
            "totalFilteredProducts": len(
                products
            ),
            "recommendedProducts": (
                public_products(products)
            ),
        }

    # ------------------------------------
    # Step 7: Database filtering
    # ------------------------------------

    database_limit = (
        limit
        if intent in {
            "lowest_price",
            "highest_price",
        }
        else 200
    )

    products = get_filtered_products(
        merged_filters,
        limit=database_limit,
    )

    # ------------------------------------
    # Step 8: No-result clarification
    # ------------------------------------

    if not products:
        response = build_no_result_clarification(
            filters=merged_filters,
            response_language=(
                response_language
            ),
            search_function=(
                get_filtered_products
            ),
        )

        response["responseLanguage"] = (
            response_language
        )
        response["filters"] = (
            merged_filters
        )
        response["queryCorrections"] = (
            all_corrections
        )

        return response

    # ------------------------------------
    # Step 9: Deterministic price intents
    # ------------------------------------

    if intent in {
        "lowest_price",
        "highest_price",
    }:
        recommendations = (
            add_price_explanations(
                products=products[:limit],
                intent=intent,
                response_language=(
                    response_language
                ),
            )
        )

        return {
            "intent": intent,
            "responseLanguage": response_language,
            "action": action,
            "filters": merged_filters,
            "queryCorrections": all_corrections,
            "sort": merged_filters.get("sort"),
            "message": localized_message(
                response_language,
                (
                    f"Here are {len(recommendations)} "
                    "price-sorted matching products."
                ),
                (
                    f"Yeh {len(recommendations)} matching "
                    "products price ke mutabiq sorted hain."
                ),
            ),
            "totalFilteredProducts": len(
                products
            ),
            "recommendedProducts": (
                public_products(
                    recommendations
                )
            ),
        }

    # ------------------------------------
    # Step 10: Semantic search
    # ------------------------------------

    semantic_query = result.get(
        "semanticQuery"
    ) or normalized_query

    embedding = generate_text_embedding(
        semantic_query
    )

    recommendations = (
        find_similar_products(
            embedding,
            products,
        )[:limit]
    )

    # ------------------------------------
    # Step 11: Low-confidence protection
    # ------------------------------------

    if semantic_result_is_low_confidence(
        recommendations
    ):
        response = (
            build_low_confidence_clarification(
                filters=merged_filters,
                response_language=(
                    response_language
                ),
                search_function=(
                    get_filtered_products
                ),
            )
        )

        response["responseLanguage"] = (
            response_language
        )
        response["filters"] = (
            merged_filters
        )
        response["queryCorrections"] = (
            all_corrections
        )

        return response

    # ------------------------------------
    # Step 12: AI explanations
    # ------------------------------------

    explanations = generate_explanations(
        original_query,
        recommendations,
        response_language=(
            response_language
        ),
    )

    for product, explanation in zip(
        recommendations,
        explanations,
    ):
        product["explanation"] = (
            explanation
        )

    return {
        "intent": intent,
        "responseLanguage": response_language,
        "action": action,
        "filters": merged_filters,
        "queryCorrections": all_corrections,
        "normalizedQuery": normalized_query,
        "semanticQuery": semantic_query,
        "message": localized_message(
            response_language,
            "Here are the matching products.",
            "Yeh aapki search se matching products hain.",
        ),
        "totalFilteredProducts": len(
            products
        ),
        "recommendedProducts": (
            public_products(
                recommendations
            )
        ),
    }




















# from fastapi import APIRouter, Query
# from pydantic import BaseModel

# from database.postgres import (
#     get_filtered_products,
#     get_chat_suggestions
# )

# from services.chat_service import parse_user_query
# from services.filter_normalizer import normalize_filters
# from services.filter_merger import merge_filters

# from database.postgres import get_filtered_products
# from database.chat_session import (
#     get_session,
#     save_session,
#     delete_session
# )

# from services.clip_service import generate_text_embedding
# from services.recommendation_service import find_similar_products
# from services.groq_service import generate_explanations


# router = APIRouter(
#     prefix="/chat",
#     tags=["Shopping Assistant"]
# )


# class ChatRequest(BaseModel):
#     sessionId: str
#     message: str



# @router.get("/suggestions")
# def chat_suggestions(
#     q: str = Query(..., min_length=1)
# ):
#     suggestions = get_chat_suggestions(q)

#     return {
#         "success": True,
#         "suggestions": suggestions
#     }



# @router.post("/search")
# def shopping_chat(request: ChatRequest):

#     # ------------------------------------
#     # Step 1 : Parse User Query
#     # ------------------------------------

#     result = parse_user_query(request.message)

#     print("\n========== PARSER RESULT ==========")
#     print(result)
#     print("===================================\n")

#     # ------------------------------------
#     # Greeting
#     # ------------------------------------

#     if result["intent"] == "greeting":

#         return {
#             "intent": "greeting",
#             "message": (
#                 "👋 Hello! I'm your AI Shopping Assistant.\n"
#                 "Tell me what product you're looking for."
#             )
#         }

#     # ------------------------------------
#     # Reset Conversation
#     # ------------------------------------

#     if result["intent"] == "reset":

#         delete_session(request.sessionId)

#         return {
#             "intent": "reset",
#             "message": "Your shopping session has been reset successfully."
#         }

#     # ------------------------------------
#     # Out Of Context
#     # ------------------------------------

#     if result["intent"] == "out_of_context":

#         return {
#             "intent": "out_of_context",
#             "message": (
#                 "Sorry, I can only help with shopping and "
#                 "product recommendations."
#             )
#         }

#     # ------------------------------------
#     # Step 2 : Normalize Filters
#     # ------------------------------------

#     current_filters = normalize_filters(
#         result.get("filters", {})
#     )

#     print("\nCurrent Filters")
#     print(current_filters)

#     # ------------------------------------
#     # Step 3 : Load Previous Session
#     # ------------------------------------

#     previous_filters = get_session(
#         request.sessionId
#     )

#     if previous_filters is None:
#         previous_filters = {}

#     print("\nPrevious Filters")
#     print(previous_filters)

#     # ------------------------------------
#     # Step 4 : Action Handling
#     # ------------------------------------

#     action = result.get("action", "new_search")

#     if action == "modify":

#         merged_filters = merge_filters(
#             previous_filters,
#             current_filters
#         )

#     else:

#         # new_search
#         merged_filters = current_filters

#     print("\nAction")
#     print(action)

#     print("\nMerged Filters")
#     print(merged_filters)

#     # ------------------------------------
#     # Step 5 : Save Session
#     # ------------------------------------

#     save_session(
#         request.sessionId,
#         merged_filters,
#         request.message
#     )

#     # ------------------------------------
#     # Step 6 : Filter Products
#     # ------------------------------------

#     products = get_filtered_products(
#         merged_filters
#     )

#     print(f"\nFiltered Products : {len(products)}")

#     if len(products) == 0:

#         return {
#             "intent": "shopping",
#             "action": action,
#             "filters": merged_filters,
#             "totalFilteredProducts": 0,
#             "recommendedProducts": [],
#             "message": "No products matched your search."
#         }

#     # ------------------------------------
#     # Step 7 : Generate Query Embedding
#     # ------------------------------------

#     embedding = generate_text_embedding(
#         request.message
#     )

#     # ------------------------------------
#     # Step 8 : Semantic Ranking
#     # ------------------------------------

#     recommendations = find_similar_products(
#         embedding,
#         products
#     )

#     # ------------------------------------
#     # Step 9 : AI Explanations
#     # ------------------------------------

#     explanations = generate_explanations(
#         request.message,
#         recommendations
#     )

#     for product, explanation in zip(
#         recommendations,
#         explanations
#     ):
#         product["explanation"] = explanation

#     # ------------------------------------
#     # Final Response
#     # ------------------------------------

#     return {

#         "intent": "shopping",

#         "action": action,

#         "filters": merged_filters,

#         "totalFilteredProducts": len(products),

#         "recommendedProducts": recommendations

#     }