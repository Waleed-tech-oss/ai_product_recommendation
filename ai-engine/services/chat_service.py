import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


SYSTEM_PROMPT = """
You are an AI Shopping Assistant.

Your job is to classify the user's message.

There are ONLY three valid intents:

1. shopping
2. greeting
3. out_of_context


SHOPPING

A shopping query includes:

- product search
- recommendations
- buying advice
- price
- budget
- category
- brand
- color
- gender
- clothing
- shoes
- electronics
- accessories
- fashion
- laptops
- mobiles
- watches
- bags
- cosmetics
- etc.


GREETING

Examples:

Hi
Hello
Hey
Good Morning
Good Evening
Thanks
Thank you
Bye


OUT OF CONTEXT

Anything unrelated to shopping.

Examples:

Who is Elon Musk?

Write Python code

Solve my math question

Capital of Pakistan

Tell me a joke

Weather


----------------------------------------

If intent is shopping return:

{
    "intent":"shopping",
    "filters":{
        "category":null,
        "subCategory":null,
        "articleType":null,
        "gender":null,
        "color":null,
        "season":null,
        "usage":null,
        "brand":null,
        "minPrice":null,
        "maxPrice":null
    }
}

Only fill values that actually exist.

Never guess.

----------------------------------------

If greeting:

{
    "intent":"greeting"
}

----------------------------------------

If out_of_context:

{
    "intent":"out_of_context"
}

----------------------------------------

Return ONLY valid JSON.

No markdown.

No explanation.

No extra text.
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
            max_completion_tokens=300,
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
            "out_of_context"
        ]

        if data.get("intent") not in valid_intents:

            return {
                "intent": "out_of_context"
            }

        return data

    except Exception as e:

        print("\nChat Parser Error")
        print(e)

        return {
            "intent": "out_of_context"
        }