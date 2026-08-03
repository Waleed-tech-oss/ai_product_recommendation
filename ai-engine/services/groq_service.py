import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_explanations(
    user_query,
    products,
    response_language="english",
):
    product_list = ""

    for index, product in enumerate(
        products,
        start=1,
    ):
        product_list += f"""
Product {index}
Title: {product.get("title")}
Vendor: {product.get("vendor")}
Product Type: {product.get("product_type")}
Price: {product.get("price")}
Similarity Score: {round(product.get("score", 0) * 100)}%
"""

    language_instruction = (
        "Write in natural Roman Urdu using Latin letters only."
        if response_language == "roman_urdu"
        else "Write in clear English."
    )

    prompt = f"""
You are an AI Shopping Assistant.

User query:
"{user_query}"

Products:
{product_list}

{language_instruction}

For each product return:
- summary: one short sentence
- reasons: exactly 4 short items

Use only the provided facts.
Never invent details.
Return only a valid JSON list.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Return clean valid JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            max_completion_tokens=900,
        )

        content = (
            response.choices[0]
            .message.content
            .strip()
        )

        if content.startswith("```"):
            content = (
                content
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        data = json.loads(content)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in (
                "products",
                "results",
                "recommendations",
            ):
                if key in data:
                    return data[key]

    except Exception as error:
        print("\n========== GROQ ERROR ==========")
        print(error)
        print("================================\n")

    explanations = []

    for product in products:
        if response_language == "roman_urdu":
            summary = (
                "Yeh aapki search ke liye relevant product hai."
            )
            default_reason = (
                "AI similarity ki bunyaad par select kiya gaya."
            )
        else:
            summary = (
                "This is a relevant product for your search."
            )
            default_reason = (
                "Selected using AI similarity."
            )

        reasons = []

        if product.get("vendor"):
            reasons.append(
                f"Vendor: {product['vendor']}."
            )

        if product.get("product_type"):
            reasons.append(
                f"Product type: {product['product_type']}."
            )

        if product.get("price") is not None:
            reasons.append(
                f"Price: ${product['price']}."
            )

        while len(reasons) < 4:
            reasons.append(default_reason)

        explanations.append({
            "summary": summary,
            "reasons": reasons[:4],
        })

    return explanations


def generate_comparison_summary(
    user_query: str,
    comparison: dict[str, Any],
    response_language: str = "english",
) -> dict[str, Any]:
    """
    Generate a concise comparison using only database facts.
    """
    products = comparison.get("products", [])
    price_summary = comparison.get(
        "priceSummary",
        {},
    )

    facts = [
        {
            "id": product.get("id"),
            "title": product.get("title"),
            "vendor": product.get("vendor"),
            "productType": product.get(
                "product_type"
            ),
            "price": product.get("price"),
            "sku": product.get("sku"),
        }
        for product in products
    ]

    language_instruction = (
        "Write in natural Roman Urdu using Latin letters only."
        if response_language == "roman_urdu"
        else "Write in clear English."
    )

    prompt = f"""
Compare the products using only the supplied facts.

User query:
{user_query}

Product facts:
{json.dumps(facts, default=str)}

Price facts:
{json.dumps(price_summary, default=str)}

{language_instruction}

Do not invent ratings, quality, materials, popularity, stock,
performance, or suitability.

Return exactly:
{{
  "summary": "short factual comparison",
  "keyPoints": ["point 1", "point 2", "point 3"]
}}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return valid JSON and use only supplied facts."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
            max_completion_tokens=450,
        )

        content = (
            response.choices[0]
            .message.content
            .strip()
        )

        if content.startswith("```"):
            content = (
                content
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        data = json.loads(content)

        if (
            isinstance(data, dict)
            and isinstance(data.get("summary"), str)
            and isinstance(data.get("keyPoints"), list)
        ):
            return {
                "summary": data["summary"],
                "keyPoints": [
                    str(point)
                    for point in data["keyPoints"][:4]
                ],
            }

    except Exception as error:
        print(
            "\n========== COMPARISON GROQ ERROR =========="
        )
        print(error)
        print(
            "===========================================\n"
        )

    cheapest = price_summary.get(
        "cheapestProductTitle"
    )
    difference = price_summary.get(
        "priceDifference"
    )

    if response_language == "roman_urdu":
        summary = (
            "Comparison available database facts par based hai."
        )
        key_points = [
            f"Kam price wala product: {cheapest}."
            if cheapest
            else "Price comparison available nahi hai.",
            f"Price difference: ${difference}."
            if difference is not None
            else "Price difference calculate nahi ho saka.",
            (
                "Ratings, reviews aur stock data database mein "
                "available nahi hain."
            ),
        ]
    else:
        summary = (
            "The comparison is based on available database facts."
        )
        key_points = [
            f"Lower-priced product: {cheapest}."
            if cheapest
            else "A price comparison is not available.",
            f"Price difference: ${difference}."
            if difference is not None
            else "The price difference could not be calculated.",
            (
                "Ratings, reviews, and inventory data are not "
                "available in the current database."
            ),
        ]

    return {
        "summary": summary,
        "keyPoints": key_points,
    }
