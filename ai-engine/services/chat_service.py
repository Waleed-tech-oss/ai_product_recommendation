import json
import os

from dotenv import load_dotenv
from groq import Groq

from services.intent_service import (
    normalize_intent_result,
)


load_dotenv()

client = Groq(
    api_key=os.getenv(
        "GROQ_API_KEY"
    )
)


SYSTEM_PROMPT = """
You are an AI Shopping Query Parser.

Understand ecommerce shopping requests written in English,
Roman Urdu, or mixed English/Roman Urdu.

Return exactly one valid JSON object.
Never answer the user.
Never explain.
Never use markdown.

Supported intents:

product_search
multi_product_search
top_products
lowest_price
highest_price
newest_products
compare_products
recommend_products
greeting
reset
out_of_context

Supported actions:

new_search
modify
reset

Supported filters:

productType
vendor
minPrice
maxPrice
priceIntent

priceIntent values:

lower
higher

Required JSON:

{
  "intent": "product_search",
  "action": "new_search",
  "limit": 5,
  "responseLanguage": "english",
  "semanticQuery": "canonical English search phrase",
  "comparisonTargets": [],
  "productTypes": [],
  "filters": {
    "productType": null,
    "vendor": null,
    "minPrice": null,
    "maxPrice": null,
    "priceIntent": null
  }
}

Rules:

1. Normalize synonyms:
   tee/t-shirt/tshirt -> shirt
   belts -> belt
   socks -> sock
   hats/caps -> cap
   sneaker/trainers -> shoe
   trouser/trousers -> pants
   snow board -> snowboard

2. Correct obvious spelling errors when meaning is clear:
   snobord -> snowboard
   shrit -> shirt
   burtan -> Burton

3. Keep vendor names in catalog-style spelling.

4. semanticQuery must be a concise English search phrase suitable
   for CLIP text embedding.

5. A clear list of product categories uses multi_product_search
   and productTypes.

   Examples:
   "shirt, belts, socks, cap"
   "show shirts and caps"
   "mujhy belt socks aur cap dikhao"

6. Do not treat a multi-category list as one productType.

7. "shirt with snowboard" is ambiguous rather than a clear list.
   Keep both concepts in productTypes. The backend will ask the
   customer to choose.

8. "Top 5 products" -> top_products.

9. "Cheapest shirts" / "saste shirts" -> lowest_price.

10. "Most expensive" / "sab se mehnge" -> highest_price.

11. "Best shoes for winter" / "mere liye suggest kro"
    -> recommend_products.

12. "Compare A and B" / "A aur B compare kro"
    -> compare_products and put clean product titles in
    comparisonTargets. Do not use productTypes for product-title
    comparison.

13. Follow-up phrases such as "sirf Burton", "under 100",
    or "aur saste" use action modify.

14. Roman Urdu input uses responseLanguage "roman_urdu".
    English input uses responseLanguage "english".

Examples:

User:
shirt, belts, socks, cap

Output:
{
  "intent": "multi_product_search",
  "action": "new_search",
  "limit": 2,
  "responseLanguage": "english",
  "semanticQuery": "shirt belt sock cap",
  "comparisonTargets": [],
  "productTypes": [
    "shirt",
    "belt",
    "sock",
    "cap"
  ],
  "filters": {}
}

User:
mujhy shirt belt socks aur cap dikhao

Output:
{
  "intent": "multi_product_search",
  "action": "new_search",
  "limit": 2,
  "responseLanguage": "roman_urdu",
  "semanticQuery": "shirt belt sock cap",
  "comparisonTargets": [],
  "productTypes": [
    "shirt",
    "belt",
    "sock",
    "cap"
  ],
  "filters": {}
}

User:
mujhy snobord dikhao

Output:
{
  "intent": "product_search",
  "action": "new_search",
  "limit": 5,
  "responseLanguage": "roman_urdu",
  "semanticQuery": "snowboard",
  "comparisonTargets": [],
  "productTypes": [
    "snowboard"
  ],
  "filters": {
    "productType": "snowboard"
  }
}

User:
Alpha Snowboard aur Beta Snowboard compare kro

Output:
{
  "intent": "compare_products",
  "action": "new_search",
  "limit": 2,
  "responseLanguage": "roman_urdu",
  "semanticQuery": "compare Alpha Snowboard and Beta Snowboard",
  "comparisonTargets": [
    "Alpha Snowboard",
    "Beta Snowboard"
  ],
  "productTypes": [],
  "filters": {}
}

Return only valid JSON.
"""


def parse_user_query(
    user_query: str,
    original_query: str | None = None,
) -> dict:
    source_query = (
        original_query
        or user_query
    )

    try:
        response = (
            client.chat.completions.create(
                model=(
                    "llama-3.3-70b-versatile"
                ),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            SYSTEM_PROMPT
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            user_query
                        ),
                    },
                ],
                temperature=0,
                max_completion_tokens=700,
            )
        )

        content = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        if content.startswith(
            "```"
        ):
            content = (
                content
                .replace(
                    "```json",
                    "",
                )
                .replace(
                    "```",
                    "",
                )
                .strip()
            )

        data = json.loads(
            content
        )

        return normalize_intent_result(
            data=data,
            user_query=source_query,
        )

    except Exception as error:
        print(
            "\n========== CHAT PARSER ERROR =========="
        )
        print(error)
        print(
            "=======================================\n"
        )

        return normalize_intent_result(
            data={
                "intent": (
                    "out_of_context"
                ),
                "action": (
                    "new_search"
                ),
                "filters": {},
                "comparisonTargets": [],
                "productTypes": [],
                "semanticQuery": (
                    user_query
                ),
            },
            user_query=source_query,
        )
