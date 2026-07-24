import os
import json

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_explanations(user_query, products):
    """
    Generate AI explanations for all recommended products
    using a single Groq API call.
    """

    product_list = ""

    for i, product in enumerate(products, start=1):

        product_list += f"""
Product {i}

Name: {product.get("name")}
Description: {product.get("description")}
Category: {product.get("category")}
Sub Category: {product.get("subCategory")}
Article Type: {product.get("articleType")}
Gender: {product.get("gender")}
Color: {product.get("color")}
Season: {product.get("season")}
Usage: {product.get("usage")}
Price: {product.get("price")}
Similarity Score: {round(product.get("score", 0) * 100)}%
"""

    prompt = f"""
You are an expert AI Shopping Assistant.

The user searched for:

"{user_query}"

Recommended Products:

{product_list}

Your task:

For EACH product generate:

1. summary (one short sentence)
2. reasons (exactly 4 short bullet points)

Rules:

- Use ONLY the provided product information.
- Never invent any facts.
- Never guess information.
- If Description is empty, ignore it.
- If any field is empty, simply ignore it.
- Mention the product's category, article type, usage, season, color or gender only if they exist.
- Consider the similarity score while writing the summary.
- Products with higher similarity should have stronger recommendations.

Return ONLY valid JSON.

Do NOT use markdown.
Do NOT use ```json.
Do NOT write any extra text.

Return exactly this structure:

[
  {{
    "summary":"Excellent match for the user's search.",
    "reasons":[
      "...",
      "...",
      "...",
      "..."
    ]
  }}
]
"""

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You always return clean valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_completion_tokens=800,
        )

        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = (
                content.replace("```json", "")
                .replace("```", "")
                .strip()
            )

        data = json.loads(content)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):

            if "products" in data:
                return data["products"]

            if "results" in data:
                return data["results"]

            if "recommendations" in data:
                return data["recommendations"]

    except Exception as e:

        print("\nGroq Error:")
        print(e)

    # ---------- FALLBACK ----------

    explanations = []

    for product in products:

        score = round(product.get("score", 0) * 100)

        if score >= 90:
            summary = "Excellent match for your search."
        elif score >= 75:
            summary = "Strong match based on semantic similarity."
        elif score >= 60:
            summary = "Relevant recommendation for your search."
        else:
            summary = "Related product based on available information."

        reasons = []

        if product.get("category"):
            reasons.append(
                f"Belongs to the {product['category']} category."
            )

        if product.get("articleType"):
            reasons.append(
                f"Product type: {product['articleType']}."
            )

        if product.get("usage"):
            reasons.append(
                f"Suitable for {product['usage']} use."
            )

        if product.get("season"):
            reasons.append(
                f"Recommended for {product['season']} season."
            )

        if product.get("color"):
            reasons.append(
                f"Available in {product['color']} color."
            )

        while len(reasons) < 4:
            reasons.append(
                "Selected using AI semantic similarity."
            )

        explanations.append({
            "summary": summary,
            "reasons": reasons[:4]
        })

    return explanations