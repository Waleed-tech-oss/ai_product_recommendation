import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from prisma import Prisma

from services.clip_service import generate_image_embedding

load_dotenv()

db = Prisma()


async def main():
    await db.connect()

    products = await db.product.find_many()

    count = 0

    for product in products:

        image_path = os.path.join(
            "../server/dataset/images",
            product.image
        )

        if not os.path.exists(image_path):
            print(f"❌ Missing: {product.image}")
            continue

        try:
            embedding = generate_image_embedding(image_path)

            await db.product.update(
                where={
                    "id": product.id
                },
                data={
                    "embedding": embedding
                }
            )

            count += 1
            print(f"✅ {count} - {product.name}")

        except Exception as e:
            print(f"❌ {product.name}")
            print(e)

    await db.disconnect()

    print("🎉 All embeddings regenerated successfully!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())