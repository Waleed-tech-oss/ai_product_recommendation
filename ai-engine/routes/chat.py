from fastapi import APIRouter, Query
from pydantic import BaseModel

from database.postgres import (
    get_filtered_products,
    get_chat_suggestions
)

from services.chat_service import parse_user_query
from services.filter_normalizer import normalize_filters
from services.filter_merger import merge_filters

from database.postgres import get_filtered_products
from database.chat_session import (
    get_session,
    save_session,
    delete_session
)

from services.clip_service import generate_text_embedding
from services.recommendation_service import find_similar_products
from services.groq_service import generate_explanations


router = APIRouter(
    prefix="/chat",
    tags=["Shopping Assistant"]
)


class ChatRequest(BaseModel):
    sessionId: str
    message: str



@router.get("/suggestions")
def chat_suggestions(
    q: str = Query(..., min_length=1)
):
    suggestions = get_chat_suggestions(q)

    return {
        "success": True,
        "suggestions": suggestions
    }



@router.post("/search")
def shopping_chat(request: ChatRequest):

    # ------------------------------------
    # Step 1 : Parse User Query
    # ------------------------------------

    result = parse_user_query(request.message)

    print("\n========== PARSER RESULT ==========")
    print(result)
    print("===================================\n")

    # ------------------------------------
    # Greeting
    # ------------------------------------

    if result["intent"] == "greeting":

        return {
            "intent": "greeting",
            "message": (
                "👋 Hello! I'm your AI Shopping Assistant.\n"
                "Tell me what product you're looking for."
            )
        }

    # ------------------------------------
    # Reset Conversation
    # ------------------------------------

    if result["intent"] == "reset":

        delete_session(request.sessionId)

        return {
            "intent": "reset",
            "message": "Your shopping session has been reset successfully."
        }

    # ------------------------------------
    # Out Of Context
    # ------------------------------------

    if result["intent"] == "out_of_context":

        return {
            "intent": "out_of_context",
            "message": (
                "Sorry, I can only help with shopping and "
                "product recommendations."
            )
        }

    # ------------------------------------
    # Step 2 : Normalize Filters
    # ------------------------------------

    current_filters = normalize_filters(
        result.get("filters", {})
    )

    print("\nCurrent Filters")
    print(current_filters)

    # ------------------------------------
    # Step 3 : Load Previous Session
    # ------------------------------------

    previous_filters = get_session(
        request.sessionId
    )

    if previous_filters is None:
        previous_filters = {}

    print("\nPrevious Filters")
    print(previous_filters)

    # ------------------------------------
    # Step 4 : Action Handling
    # ------------------------------------

    action = result.get("action", "new_search")

    if action == "modify":

        merged_filters = merge_filters(
            previous_filters,
            current_filters
        )

    else:

        # new_search
        merged_filters = current_filters

    print("\nAction")
    print(action)

    print("\nMerged Filters")
    print(merged_filters)

    # ------------------------------------
    # Step 5 : Save Session
    # ------------------------------------

    save_session(
        request.sessionId,
        merged_filters,
        request.message
    )

    # ------------------------------------
    # Step 6 : Filter Products
    # ------------------------------------

    products = get_filtered_products(
        merged_filters
    )

    print(f"\nFiltered Products : {len(products)}")

    if len(products) == 0:

        return {
            "intent": "shopping",
            "action": action,
            "filters": merged_filters,
            "totalFilteredProducts": 0,
            "recommendedProducts": [],
            "message": "No products matched your search."
        }

    # ------------------------------------
    # Step 7 : Generate Query Embedding
    # ------------------------------------

    embedding = generate_text_embedding(
        request.message
    )

    # ------------------------------------
    # Step 8 : Semantic Ranking
    # ------------------------------------

    recommendations = find_similar_products(
        embedding,
        products
    )

    # ------------------------------------
    # Step 9 : AI Explanations
    # ------------------------------------

    explanations = generate_explanations(
        request.message,
        recommendations
    )

    for product, explanation in zip(
        recommendations,
        explanations
    ):
        product["explanation"] = explanation

    # ------------------------------------
    # Final Response
    # ------------------------------------

    return {

        "intent": "shopping",

        "action": action,

        "filters": merged_filters,

        "totalFilteredProducts": len(products),

        "recommendedProducts": recommendations

    }