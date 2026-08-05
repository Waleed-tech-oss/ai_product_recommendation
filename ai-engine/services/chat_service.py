import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from pydantic import ValidationError

from services.intent_service import detect_response_language, normalize_intent_result
from services.parser_schema import ShoppingQueryPlan
from services.query_normalizer import (
    classify_product_type_request,
    detect_product_type_mentions,
)


load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = os.getenv("GROQ_QUERY_MODEL", "llama-3.3-70b-versatile")
MAX_CATALOG_CONTEXT_ITEMS = int(os.getenv("MAX_CATALOG_CONTEXT_ITEMS", "200"))


BASE_SYSTEM_PROMPT = """
You are an ecommerce shopping query planner.

Understand English, Roman Urdu, and mixed queries.
Return exactly one JSON object. Do not answer the customer. Do not use markdown.

The supplied current-shop catalog context is the only source of truth for
product types and vendors. Never invent a product type or vendor.

Put catalog-resolved categories in productTypes.
Put category words absent from the catalog in unresolvedProductTypes.

Never map an unknown specific product term to a broader catalog type.
For example, when the user asks for "helmet" but the catalog only
contains "Accessories", return:
productTypes: []
unresolvedProductTypes: ["helmet"]

Only resolve a product type when the user term matches an actual
catalog type, a supplied catalog alias, or a clear spelling/plural
form of an actual catalog type.

Supported intents:
product_search, multi_product_search, top_products, lowest_price,
highest_price, newest_products, compare_products, recommend_products,
greeting, reset, out_of_context

Supported actions: new_search, modify, reset
Supported relation values: none, single, multi_list, ambiguous, complementary

Relationship rules:
- One category -> single
- A clear comma-separated or and/aur category list -> multi_list
- An unclear relationship between categories -> ambiguous
- A product requested for use with another product -> complementary
- Product-title comparison -> compare_products

Do not convert a clear category list into one product type.
Do not place full product titles in productTypes.
comparisonTargets is only for product-title comparison.
Follow-up constraints that depend on prior results use action modify.
semanticQuery must be a concise English retrieval phrase.

Return every key in this shape:
{
  "intent": "product_search",
  "action": "new_search",
  "limit": 5,
  "responseLanguage": "english",
  "semanticQuery": "",
  "comparisonTargets": [],
  "productTypes": [],
  "unresolvedProductTypes": [],
  "relation": "none",
  "filters": {
    "productType": null,
    "vendor": null,
    "minPrice": null,
    "maxPrice": null,
    "priceIntent": null
  }
}
"""


def _clean_catalog_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean_value = " ".join(str(value or "").strip().split())
        key = clean_value.lower()
        if not clean_value or key in seen:
            continue
        seen.add(key)
        result.append(clean_value)
        if len(result) >= MAX_CATALOG_CONTEXT_ITEMS:
            break
    return result


def _catalog_context(vocabulary: dict[str, Any] | None) -> dict[str, Any]:
    vocabulary = vocabulary or {}
    aliases = vocabulary.get("aliases", {})

    if isinstance(aliases, list):
        aliases = aliases[:MAX_CATALOG_CONTEXT_ITEMS]
    elif isinstance(aliases, dict):
        aliases = dict(list(aliases.items())[:MAX_CATALOG_CONTEXT_ITEMS])
    else:
        aliases = {}

    return {
        "productTypes": _clean_catalog_values(vocabulary.get("product_types", [])),
        "vendors": _clean_catalog_values(vocabulary.get("vendors", [])),
        "aliases": aliases,
    }


def _validate_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return ShoppingQueryPlan.model_validate(payload).model_dump()


def _groq_json_request(messages: list[dict[str, str]]) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0,
        max_completion_tokens=700,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content.strip()


def _deterministic_fallback(
    user_query: str,
    source_query: str,
    vocabulary: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    mentions = detect_product_type_mentions(user_query, vocabulary)
    relation = classify_product_type_request(user_query, mentions)

    if len(mentions) >= 2:
        intent = "multi_product_search" if relation == "multi_list" else "product_search"
    elif len(mentions) == 1:
        intent = "product_search"
    else:
        intent = "out_of_context"

    filters: dict[str, Any] = {}
    if len(mentions) == 1:
        filters["productType"] = mentions[0]

    fallback = {
        "intent": intent,
        "action": "new_search",
        "limit": 5,
        "responseLanguage": detect_response_language(source_query),
        "semanticQuery": user_query,
        "comparisonTargets": [],
        "productTypes": mentions,
        "unresolvedProductTypes": [],
        "relation": relation,
        "filters": filters,
        "parserStatus": "fallback",
        "parserError": type(error).__name__,
    }
    return normalize_intent_result(fallback, source_query)


def parse_user_query(
    user_query: str,
    original_query: str | None = None,
    vocabulary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_query = original_query or user_query
    catalog_json = json.dumps(_catalog_context(vocabulary), ensure_ascii=False)

    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"CURRENT SHOP CATALOG CONTEXT:\n{catalog_json}",
        },
        {"role": "user", "content": user_query},
    ]

    try:
        content = _groq_json_request(messages)
        validated = _validate_plan(json.loads(content))
        validated["parserStatus"] = "validated"
        return normalize_intent_result(validated, source_query)

    except (json.JSONDecodeError, ValidationError) as first_error:
        try:
            repair_messages = [
                *messages,
                {"role": "assistant", "content": content if "content" in locals() else "{}"},
                {
                    "role": "user",
                    "content": (
                        "The previous JSON failed schema validation. Return a corrected "
                        "JSON object with every required key and no commentary. "
                        f"Validation error: {first_error}"
                    ),
                },
            ]
            repaired_content = _groq_json_request(repair_messages)
            validated = _validate_plan(json.loads(repaired_content))
            validated["parserStatus"] = "repaired"
            return normalize_intent_result(validated, source_query)
        except Exception as repair_error:
            print("\n========== CHAT PARSER REPAIR ERROR ==========")
            print(repair_error)
            print("==============================================\n")
            return _deterministic_fallback(
                user_query,
                source_query,
                vocabulary or {},
                repair_error,
            )

    except Exception as error:
        print("\n========== CHAT PARSER ERROR ==========")
        print(error)
        print("=======================================\n")
        return _deterministic_fallback(
            user_query,
            source_query,
            vocabulary or {},
            error,
        )
