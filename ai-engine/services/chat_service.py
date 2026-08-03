import json
import os

from dotenv import load_dotenv
from groq import Groq

from services.intent_service import (
    normalize_intent_result,
)


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
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
   sneaker/trainers -> shoe
   trouser/trousers -> pants
   snow board -> snowboard

2. Correct obvious spelling errors when meaning is clear:
   snobord -> snowboard
   shrit -> shirt
   burtan -> Burton

3. Keep vendor names in their catalog-style spelling.

4. semanticQuery must be a concise English search phrase suitable for
   CLIP text embedding.

5. "Top 5 products" -> top_products.

6. "Cheapest shirts" / "saste shirts" -> lowest_price.

7. "Most expensive" / "sab se mehnge" -> highest_price.

8. "Best shoes for winter" / "mere liye suggest kro"
   -> recommend_products.

9. "Compare A and B" / "A aur B compare kro"
   -> compare_products and put clean product names in comparisonTargets.

10. "shirt with snowboard" is potentially ambiguous. Keep both concepts in
    semanticQuery. The backend will ask a clarification if both are catalog
    product types.

11. Follow-up phrases such as "medium", "sirf Burton", "under 100",
    or "aur saste" use action modify.

12. Roman Urdu input uses responseLanguage "roman_urdu".
    English input uses "english".

Examples:

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
  "filters": {
    "productType": "snowboard"
  }
}

User:
mujhy 3 saste t shirts dikhao

Output:
{
  "intent": "lowest_price",
  "action": "new_search",
  "limit": 3,
  "responseLanguage": "roman_urdu",
  "semanticQuery": "cheap shirt",
  "comparisonTargets": [],
  "filters": {
    "productType": "shirt"
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
  "filters": {}
}

Return only valid JSON.
"""


def parse_user_query(
    user_query: str,
    original_query: str | None = None,
) -> dict:
    """
    user_query:
        Synonym/typo-normalized query sent to Groq.

    original_query:
        Original customer message used for Roman Urdu detection and
        deterministic intent rules.
    """
    source_query = original_query or user_query

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_query,
                },
            ],
            temperature=0,
            max_completion_tokens=600,
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
                "intent": "out_of_context",
                "action": "new_search",
                "filters": {},
                "comparisonTargets": [],
                "semanticQuery": user_query,
            },
            user_query=source_query,
        )


































# import json
# import os

# from dotenv import load_dotenv
# from groq import Groq

# load_dotenv()

# client = Groq(
#     api_key=os.getenv("GROQ_API_KEY")
# )
# SYSTEM_PROMPT = """
# You are an AI Shopping Query Parser.

# Your ONLY job is to understand shopping conversations
# and return VALID JSON.

# Never explain.
# Never answer questions.
# Never use markdown.

# ----------------------------------------
# Supported Intents
# ----------------------------------------

# shopping
# greeting
# out_of_context
# reset

# ----------------------------------------
# Supported Actions
# ----------------------------------------

# new_search
# modify
# reset

# ----------------------------------------
# Supported Shopify Filters
# ----------------------------------------

# productType
# vendor
# minPrice
# maxPrice
# priceIntent

# priceIntent values:

# lower
# higher

# ----------------------------------------
# Examples
# ----------------------------------------

# User:
# Show me snowboards

# Output:

# {
#   "intent":"shopping",
#   "action":"new_search",
#   "filters":{
#       "productType":"snowboard",
#       "vendor":null,
#       "minPrice":null,
#       "maxPrice":null,
#       "priceIntent":null
#   }
# }

# ----------------------------------------

# User:
# Show Nike products

# Output:

# {
#   "intent":"shopping",
#   "action":"new_search",
#   "filters":{
#       "productType":null,
#       "vendor":"Nike",
#       "minPrice":null,
#       "maxPrice":null,
#       "priceIntent":null
#   }
# }

# ----------------------------------------

# User:
# Snowboards under 700

# Output:

# {
#   "intent":"shopping",
#   "action":"new_search",
#   "filters":{
#       "productType":"snowboard",
#       "vendor":null,
#       "minPrice":null,
#       "maxPrice":700,
#       "priceIntent":null
#   }
# }

# ----------------------------------------

# User:
# Only Burton

# Output:

# {
#   "intent":"shopping",
#   "action":"modify",
#   "filters":{
#       "vendor":"Burton"
#   }
# }

# ----------------------------------------

# User:
# Show cheaper ones

# Output:

# {
#   "intent":"shopping",
#   "action":"modify",
#   "filters":{
#       "priceIntent":"lower"
#   }
# }

# ----------------------------------------

# User:
# Show premium products

# Output:

# {
#   "intent":"shopping",
#   "action":"modify",
#   "filters":{
#       "priceIntent":"higher"
#   }
# }

# ----------------------------------------

# User:
# Start over

# Output:

# {
#   "intent":"reset",
#   "action":"reset",
#   "filters":{}
# }

# ----------------------------------------

# User:
# Hello

# Output:

# {
#   "intent":"greeting",
#   "action":"new_search"
# }

# ----------------------------------------

# User:
# Who is Elon Musk?

# Output:

# {
#   "intent":"out_of_context",
#   "action":"new_search"
# }

# ----------------------------------------

# Return ONLY valid JSON.

# No markdown.
# No explanation.
# """


# def parse_user_query(user_query: str):

#     try:

#         response = client.chat.completions.create(
#             model="llama-3.3-70b-versatile",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": SYSTEM_PROMPT
#                 },
#                 {
#                     "role": "user",
#                     "content": user_query
#                 }
#             ],
#             temperature=0,
#             max_completion_tokens=400,
#         )

#         content = response.choices[0].message.content.strip()

#         if content.startswith("```"):
#             content = (
#                 content.replace("```json", "")
#                 .replace("```", "")
#                 .strip()
#             )

#         data = json.loads(content)

#         valid_intents = [
#             "shopping",
#             "greeting",
#             "out_of_context",
#             "reset"
#         ]

#         valid_actions = [
#             "new_search",
#             "modify",
#             "reset"
#         ]

#         if data.get("intent") not in valid_intents:
#             data["intent"] = "out_of_context"

#         if data.get("action") not in valid_actions:
#             data["action"] = "new_search"

#         if "filters" not in data:
#             data["filters"] = {}

#         return data

#     except Exception as e:

#         print("\n========== CHAT PARSER ERROR ==========")
#         print(e)
#         print("=======================================\n")

#         return {
#             "intent": "out_of_context",
#             "action": "new_search",
#             "filters": {}
#         }