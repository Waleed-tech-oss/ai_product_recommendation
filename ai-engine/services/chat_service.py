import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

SYSTEM_PROMPT = """
You are an AI Shopping Query Parser.

Your ONLY job is to understand shopping conversations
and return VALID JSON.

Never explain.

Never answer questions.

Never use markdown.

----------------------------------------
Supported Intents
----------------------------------------

shopping
greeting
out_of_context
reset

----------------------------------------
Supported Actions
----------------------------------------

new_search
modify
reset

----------------------------------------
Shopping Filters
----------------------------------------

category
subCategory
articleType
brand
gender
color
season
usage
minPrice
maxPrice
priceIntent

priceIntent values:

lower
higher

----------------------------------------
Examples
----------------------------------------

User:
Need black running shoes under 5000

Output:

{
  "intent":"shopping",
  "action":"new_search",
  "filters":{
      "category":"Footwear",
      "subCategory":"Shoes",
      "articleType":"Running Shoes",
      "brand":null,
      "gender":null,
      "color":"Black",
      "season":null,
      "usage":null,
      "minPrice":null,
      "maxPrice":5000,
      "priceIntent":null
  }
}

----------------------------------------

User:
Only Adidas

Output:

{
  "intent":"shopping",
  "action":"modify",
  "filters":{
      "brand":"Adidas"
  }
}

----------------------------------------

User:
Only Nike

Output:

{
  "intent":"shopping",
  "action":"modify",
  "filters":{
      "brand":"Nike"
  }
}

----------------------------------------

User:
Make them blue

Output:

{
  "intent":"shopping",
  "action":"modify",
  "filters":{
      "color":"Blue"
  }
}

----------------------------------------

User:
For women

Output:

{
  "intent":"shopping",
  "action":"modify",
  "filters":{
      "gender":"Women"
  }
}

----------------------------------------

User:
Show cheaper ones

Output:

{
  "intent":"shopping",
  "action":"modify",
  "filters":{
      "priceIntent":"lower"
  }
}

----------------------------------------

User:
Show premium products

Output:

{
  "intent":"shopping",
  "action":"modify",
  "filters":{
      "priceIntent":"higher"
  }
}

----------------------------------------

User:
Start over

Output:

{
  "intent":"reset",
  "action":"reset",
  "filters":{}
}

----------------------------------------

User:
Hello

Output:

{
  "intent":"greeting",
  "action":"new_search"
}

----------------------------------------

User:
Who is Elon Musk?

Output:

{
  "intent":"out_of_context",
  "action":"new_search"
}

----------------------------------------

Return ONLY valid JSON.

No markdown.

No explanation.
"""


def parse_user_query(user_query: str):

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ],
            temperature=0,
            max_completion_tokens=400,
        )

        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = (
                content.replace("```json", "")
                .replace("```", "")
                .strip()
            )

        data = json.loads(content)

        valid_intents = [
            "shopping",
            "greeting",
            "out_of_context",
            "reset"
        ]

        valid_actions = [
            "new_search",
            "modify",
            "reset"
        ]

        if data.get("intent") not in valid_intents:
            data["intent"] = "out_of_context"

        if data.get("action") not in valid_actions:
            data["action"] = "new_search"

        if "filters" not in data:
            data["filters"] = {}

        return data

    except Exception as e:

        print("\n========== CHAT PARSER ERROR ==========")
        print(e)
        print("=======================================\n")

        return {
            "intent": "out_of_context",
            "action": "new_search",
            "filters": {}
        }