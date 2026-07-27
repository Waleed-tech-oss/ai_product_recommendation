import os

from dotenv import load_dotenv
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from database.postgres import get_all_products
from services.clip_service import (
    generate_embedding,
    generate_text_embedding,
)
from services.recommendation_service import (
    find_similar_products,
    get_more_like_this
)
from services.groq_service import generate_explanations

load_dotenv()

router = APIRouter()


# --------------------------------
# Request Model
# --------------------------------
class TextSearchRequest(BaseModel):
    query: str

# --------------------------------
# More Like This Request
# --------------------------------

class MoreLikeThisRequest(BaseModel):
    productId: str

# --------------------------------
# Image Recommendation
# --------------------------------
@router.post("/recommend")
async def recommend(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)

    temp_path = f"uploads/{file.filename}"

    try:
        with open(temp_path, "wb") as buffer:
            buffer.write(await file.read())

        # Generate Image Embedding
        embedding = generate_embedding(temp_path)

        # Fetch Products
        products = get_all_products()

        # Find Similar Products
        recommendations = find_similar_products(
            embedding,
            products
        )

        # Generate AI Explanations (Single Groq Call)
        explanations = generate_explanations(
            "Uploaded Image",
            recommendations
        )

        # Attach explanation to each product
        for product, explanation in zip(recommendations, explanations):
            product["explanation"] = explanation

        return recommendations

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# --------------------------------
# Text Recommendation
# --------------------------------
@router.post("/search/text")
async def text_search(request: TextSearchRequest):
    try:

        # Generate Text Embedding
        embedding = generate_text_embedding(request.query)

        # Fetch Products
        products = get_all_products()
        print(products[0])

        # Find Similar Products
        recommendations = find_similar_products(
            embedding,
            products
        )

        # Generate AI Explanations (Single Groq Call)
        explanations = generate_explanations(
            request.query,
            recommendations
        )

        # Attach explanation to each product
        for product, explanation in zip(recommendations, explanations):
            product["explanation"] = explanation

        return recommendations

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



# --------------------------------
# More Like This
# --------------------------------

@router.post("/more-like-this")
async def more_like_this(request: MoreLikeThisRequest):

    try:

        recommendations = get_more_like_this(
            request.productId
        )

        return {
            "success": True,
            "totalRecommendations": len(recommendations),
            "recommendedProducts": recommendations
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )        