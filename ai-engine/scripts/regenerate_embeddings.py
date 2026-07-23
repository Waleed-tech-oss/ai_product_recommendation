import os
import sys
import json
import psycopg

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from dotenv import load_dotenv
from services.clip_service import generate_image_embedding

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

IMAGE_FOLDER = "../server/dataset/images"

conn = psycopg.connect(DATABASE_URL)

with conn.cursor() as cur:

    cur.execute("""
        SELECT id, image, name
        FROM products
    """)

    products = cur.fetchall()

    print(f"📦 Found {len(products)} products")

    count = 0

    for product_id, image_name, name in products:

        image_path = os.path.join(
            IMAGE_FOLDER,
            image_name
        )

        if not os.path.exists(image_path):
            print(f"❌ Missing image: {image_name}")
            continue

        try:

            embedding = generate_image_embedding(image_path)

            cur.execute(
                """
                UPDATE products
                SET embedding = %s::jsonb
                WHERE id = %s
                """,
                (
                    json.dumps(embedding),
                    product_id
                )
            )

            conn.commit()

            count += 1

            print(f"✅ {count} - {name}")

        except Exception as e:

            conn.rollback()

            print(f"\n❌ Failed: {name}")
            print(type(e).__name__)
            print(e)
            break

conn.close()

print(f"\n🎉 Successfully regenerated {count} embeddings.")