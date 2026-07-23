import os

from dotenv import load_dotenv
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from database.postgres import get_all_products
from services.clip_service import (
    generate_embedding,
    generate_text_embedding,
)
from services.recommendation_service import find_similar_products

load_dotenv()

router = APIRouter()


# -----------------------------
# Request Model for Text Search
# -----------------------------
class TextSearchRequest(BaseModel):
    query: str


# -----------------------------
# Image Recommendation
# -----------------------------
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

        return recommendations

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# -----------------------------
# Text Recommendation
# -----------------------------
@router.post("/search/text")
async def text_search(request: TextSearchRequest):
    try:
        # Generate Text Embedding
        embedding = generate_text_embedding(request.query)

        # Fetch Products
        products = get_all_products()

        # Find Similar Products
        recommendations = find_similar_products(
            embedding,
            products
        )

        return recommendations

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )