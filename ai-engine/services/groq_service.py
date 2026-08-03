import os
import json

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# ----------------------------------------
# Generate AI Explanations
# ----------------------------------------

def generate_explanations(user_query, products):
    """
    Generate AI explanations for Shopify product recommendations
    using a single Groq API call.
    """

    product_list = ""

    for i, product in enumerate(products, start=1):

        product_list += f"""
Product {i}

Title: {product.get("title")}
Vendor: {product.get("vendor")}
Product Type: {product.get("product_type")}
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
- Ignore missing fields.
- Mention Vendor if available.
- Mention Product Type if available.
- Mention Price if available.
- Consider the similarity score while writing the recommendation.
- Products with higher similarity should receive stronger recommendations.

Return ONLY valid JSON.

Do NOT use markdown.
Do NOT use ```json.
Do NOT write any extra text.

Return exactly this structure:

[
  {{
    "summary": "Excellent match for the uploaded image.",
    "reasons": [
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

        print("\n========== GROQ ERROR ==========")
        print(e)
        print("================================\n")

    # ----------------------------------------
    # Fallback Explanations
    # ----------------------------------------

    explanations = []

    for product in products:

        score = round(product.get("score", 0) * 100)

        if score >= 90:
            summary = "Excellent match for your uploaded image."
        elif score >= 75:
            summary = "Strong visual similarity to your uploaded image."
        elif score >= 60:
            summary = "Relevant recommendation based on AI similarity."
        else:
            summary = "Related product based on available visual information."

        reasons = []

        if product.get("vendor"):
            reasons.append(
                f"Sold by {product['vendor']}."
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
            reasons.append(
                "Selected using AI visual similarity."
            )

        explanations.append({
            "summary": summary,
            "reasons": reasons[:4]
        })

    return explanations