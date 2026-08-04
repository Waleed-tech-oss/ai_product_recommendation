from __future__ import annotations

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from database.chat_session import (
    get_session,
    save_session,
)
from database.postgres import (
    get_catalog_vocabulary,
    get_filtered_products,
)

from services.chat_service import (
    parse_user_query,
)
from services.clarification_service import (
    build_no_result_clarification,
)
from services.clip_service import (
    generate_image_embedding,
    generate_text_embedding,
)
from services.filter_merger import (
    merge_filters,
)
from services.filter_normalizer import (
    normalize_filters,
)
from services.groq_service import (
    generate_explanations,
)
from services.image_search_service import (
    ImageValidationError,
    build_visual_confidence_response,
    has_meaningful_visual_text,
    validate_image_bytes,
    visual_result_is_low_confidence,
)
from services.intent_service import (
    detect_response_language,
)
from services.query_normalizer import (
    normalize_filter_values,
    normalize_query_text,
)
from services.recommendation_service import (
    find_hybrid_shopify_products,
)


router = APIRouter(
    prefix="/chat",
    tags=["Shopping Assistant"],
)


def localized(
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


@router.post("/image-search")
async def image_chat_search(
    sessionId: str = Form(...),
    message: str = Form(""),
    image: UploadFile = File(...),
):
    """
    Pure image search:
        image + empty message

    Image/text hybrid search:
        image + natural-language message

    The Shopify product embeddings already stored in PostgreSQL are
    image embeddings, so no database migration is required.
    """
    original_message = " ".join(
        (message or "").strip().split()
    )

    response_language = (
        detect_response_language(
            original_message
        )
        if original_message
        else "english"
    )

    content = await image.read()

    try:
        image_metadata = (
            validate_image_bytes(
                content=content,
                content_type=(
                    image.content_type
                ),
            )
        )
    except ImageValidationError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    try:
        image_embedding = (
            generate_image_embedding(
                content
            )
        )
    except Exception as error:
        print(
            "\n========== IMAGE EMBEDDING ERROR =========="
        )
        print(error)
        print(
            "===========================================\n"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The image could not be processed by CLIP."
            ),
        ) from error

    vocabulary = get_catalog_vocabulary()

    query_corrections = []
    normalized_query = ""
    semantic_query = ""
    current_filters = {}
    action = "new_search"
    original_intent = "visual_search"
    limit = 5
    use_text_embedding = False
    text_embedding = None

    if original_message:
        (
            normalized_query,
            query_corrections,
        ) = normalize_query_text(
            original_message,
            vocabulary,
        )

        parsed = parse_user_query(
            normalized_query,
            original_query=(
                original_message
            ),
        )

        response_language = parsed.get(
            "responseLanguage",
            response_language,
        )
        action = parsed.get(
            "action",
            "new_search",
        )
        original_intent = parsed.get(
            "intent",
            "product_search",
        )
        limit = parsed.get("limit", 5)

        current_filters = (
            normalize_filters(
                parsed.get(
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

        query_corrections.extend(
            filter_corrections
        )

        semantic_query = (
            parsed.get("semanticQuery")
            or normalized_query
        )

        use_text_embedding = (
            has_meaningful_visual_text(
                original_message=(
                    original_message
                ),
                semantic_query=(
                    semantic_query
                ),
            )
        )

        if use_text_embedding:
            try:
                text_embedding = (
                    generate_text_embedding(
                        semantic_query
                    )
                )
            except Exception as error:
                # Visual search can still continue if text embedding
                # generation fails.
                print(
                    "\n========== HYBRID TEXT EMBEDDING ERROR =========="
                )
                print(error)
                print(
                    "=================================================\n"
                )
                text_embedding = None
                use_text_embedding = False

    previous_filters = (
        get_session(sessionId)
        or {}
    )

    if (
        original_message
        and action == "modify"
    ):
        merged_filters = merge_filters(
            previous_filters,
            current_filters,
        )
    else:
        # An image-only request starts a fresh visual search.
        merged_filters = (
            current_filters
            if original_message
            else {}
        )

    save_session(
        sessionId,
        merged_filters,
        (
            original_message
            or "Uploaded image search"
        ),
    )

    products = get_filtered_products(
        merged_filters,
        limit=200,
    )

    if not products:
        response = (
            build_no_result_clarification(
                filters=merged_filters,
                response_language=(
                    response_language
                ),
                search_function=(
                    get_filtered_products
                ),
            )
        )

        response.update({
            "responseLanguage": (
                response_language
            ),
            "searchMode": (
                "image_with_filters"
            ),
            "filters": merged_filters,
            "queryCorrections": (
                query_corrections
            ),
            "imageMetadata": (
                image_metadata
            ),
        })

        return response

    recommendations = (
        find_hybrid_shopify_products(
            image_embedding=(
                image_embedding
            ),
            text_embedding=(
                text_embedding
                if use_text_embedding
                else None
            ),
            products=products,
            top_k=limit,
            infer_product_type=(
                not bool(
                    merged_filters.get(
                        "productType"
                    )
                )
            ),
        )
    )

    if visual_result_is_low_confidence(
        recommendations
    ):
        response = (
            build_visual_confidence_response(
                response_language=(
                    response_language
                ),
                filters=merged_filters,
            )
        )

        response.update({
            "queryCorrections": (
                query_corrections
            ),
            "imageMetadata": (
                image_metadata
            ),
        })

        return response

    inferred_product_type = (
        recommendations[0].get(
            "inferredProductType"
        )
        if recommendations
        else None
    )

    if use_text_embedding:
        search_mode = (
            "image_text_hybrid"
        )
    elif merged_filters:
        search_mode = (
            "image_with_filters"
        )
    else:
        search_mode = "image_only"

    explanation_query = (
        original_message
        or "Uploaded image visual search"
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
        product["explanation"] = (
            explanation
        )

    return {
        "intent": "visual_search",
        "originalIntent": (
            original_intent
        ),
        "searchMode": search_mode,
        "responseLanguage": (
            response_language
        ),
        "message": localized(
            response_language,
            (
                "Here are the products that best match "
                "your uploaded image."
                if search_mode == "image_only"
                else (
                    "Here are products ranked using your "
                    "image and shopping instructions."
                )
            ),
            (
                "Yeh uploaded image se sab se zyada "
                "matching products hain."
                if search_mode == "image_only"
                else (
                    "Yeh products aapki image aur shopping "
                    "instructions dono ko use karke rank kiye gaye hain."
                )
            ),
        ),
        "filters": merged_filters,
        "inferredProductType": (
            inferred_product_type
        ),
        "queryCorrections": (
            query_corrections
        ),
        "normalizedQuery": (
            normalized_query
            or None
        ),
        "semanticQuery": (
            semantic_query
            if use_text_embedding
            else None
        ),
        "imageMetadata": image_metadata,
        "rankingWeights": {
            "image": (
                0.70
                if use_text_embedding
                else 1.0
            ),
            "text": (
                0.30
                if use_text_embedding
                else 0.0
            ),
        },
        "totalFilteredProducts": len(
            products
        ),
        "recommendedProducts": (
            recommendations
        ),
    }
