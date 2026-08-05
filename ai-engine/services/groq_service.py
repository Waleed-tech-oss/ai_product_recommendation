import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field, ValidationError


load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = os.getenv("GROQ_EXPLANATION_MODEL", "llama-3.3-70b-versatile")


class ProductExplanation(BaseModel):
    summary: str
    reasons: list[str] = Field(default_factory=list, max_length=4)


class ExplanationEnvelope(BaseModel):
    explanations: list[ProductExplanation]


class ComparisonEnvelope(BaseModel):
    summary: str
    keyPoints: list[str] = Field(default_factory=list, max_length=4)


def _currency(product: dict[str, Any]) -> str:
    code = product.get("currency_code") or ""
    price = product.get("price")
    return f"{code} {price}".strip() if price is not None else "Unavailable"


def _request_json(messages, max_tokens):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0,
        max_completion_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content.strip())


def generate_explanations(user_query, products, response_language="english"):
    facts = [
        {
            "title": product.get("title"),
            "vendor": product.get("vendor"),
            "productType": product.get("product_type"),
            "taxonomy": product.get("taxonomy_category_full_name"),
            "price": product.get("price"),
            "currencyCode": product.get("currency_code"),
            "availableForSale": product.get("available_for_sale"),
            "score": product.get("score"),
            "lexicalScore": product.get("lexicalScore"),
            "textScore": product.get("textScore"),
            "imageScore": product.get("imageScore"),
        }
        for product in products
    ]

    language_instruction = (
        "Write natural Roman Urdu using Latin letters only."
        if response_language == "roman_urdu"
        else "Write clear English."
    )

    prompt = f"""
User query: {user_query}
Product facts: {json.dumps(facts, default=str)}

{language_instruction}
Use only supplied facts. Never invent material, quality, popularity,
rating, suitability, stock detail, or features.

Return this JSON object:
{{
  "explanations": [
    {{
      "summary": "one short factual sentence",
      "reasons": ["reason 1", "reason 2", "reason 3", "reason 4"]
    }}
  ]
}}
Return one explanation per supplied product in the same order.
"""

    try:
        payload = _request_json(
            [
                {
                    "role": "system",
                    "content": "Return one valid JSON object matching the requested structure.",
                },
                {"role": "user", "content": prompt},
            ],
            1000,
        )
        validated = ExplanationEnvelope.model_validate(payload)
        explanations = [item.model_dump() for item in validated.explanations]
        if len(explanations) == len(products):
            return explanations

    except (json.JSONDecodeError, ValidationError, Exception) as error:
        print("\n========== GROQ EXPLANATION ERROR ==========")
        print(error)
        print("============================================\n")

    fallback = []
    for product in products:
        if response_language == "roman_urdu":
            summary = "Yeh product available catalog facts ki bunyaad par aapki search se match karta hai."
            reasons = [
                f"Product type: {product.get('product_type') or 'available nahi'}.",
                f"Vendor: {product.get('vendor') or 'available nahi'}.",
                f"Price: {_currency(product)}.",
                "Search ranking title, catalog text aur semantic relevance se bani hai.",
            ]
        else:
            summary = "This product matches your search based on the available catalog facts."
            reasons = [
                f"Product type: {product.get('product_type') or 'unavailable'}.",
                f"Vendor: {product.get('vendor') or 'unavailable'}.",
                f"Price: {_currency(product)}.",
                "The ranking uses title, catalog text, and semantic relevance.",
            ]
        fallback.append({"summary": summary, "reasons": reasons[:4]})

    return fallback


def generate_comparison_summary(
    user_query: str,
    comparison: dict[str, Any],
    response_language: str = "english",
) -> dict[str, Any]:
    products = comparison.get("products", [])
    price_summary = comparison.get("priceSummary", {})

    facts = [
        {
            "id": product.get("id"),
            "title": product.get("title"),
            "vendor": product.get("vendor"),
            "productType": product.get("product_type"),
            "taxonomy": product.get("taxonomy_category_full_name"),
            "price": product.get("price"),
            "currencyCode": product.get("currency_code"),
            "sku": product.get("sku"),
            "availableForSale": product.get("available_for_sale"),
        }
        for product in products
    ]

    language_instruction = (
        "Write natural Roman Urdu using Latin letters only."
        if response_language == "roman_urdu"
        else "Write clear English."
    )

    prompt = f"""
Compare products using only these facts.
User query: {user_query}
Product facts: {json.dumps(facts, default=str)}
Price facts: {json.dumps(price_summary, default=str)}
{language_instruction}

Return exactly:
{{"summary":"short factual comparison","keyPoints":["point 1","point 2","point 3"]}}
"""

    try:
        payload = _request_json(
            [
                {"role": "system", "content": "Return one valid JSON object using only supplied facts."},
                {"role": "user", "content": prompt},
            ],
            500,
        )
        return ComparisonEnvelope.model_validate(payload).model_dump()

    except Exception as error:
        print("\n========== COMPARISON GROQ ERROR ==========")
        print(error)
        print("===========================================\n")

    cheapest = price_summary.get("cheapestProductTitle")
    difference = price_summary.get("priceDifference")

    if response_language == "roman_urdu":
        return {
            "summary": "Comparison available database facts par based hai.",
            "keyPoints": [
                f"Kam price wala product: {cheapest}." if cheapest else "Price comparison available nahi hai.",
                f"Price difference: {difference}." if difference is not None else "Price difference calculate nahi ho saka.",
                "Unavailable product facts invent nahi kiye gaye.",
            ],
        }

    return {
        "summary": "The comparison is based on available database facts.",
        "keyPoints": [
            f"Lower-priced product: {cheapest}." if cheapest else "A price comparison is not available.",
            f"Price difference: {difference}." if difference is not None else "The price difference could not be calculated.",
            "Unavailable product facts were not invented.",
        ],
    }
