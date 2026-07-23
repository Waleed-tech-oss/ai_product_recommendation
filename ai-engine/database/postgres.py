import os
import json
import psycopg

from dotenv import load_dotenv

load_dotenv()

conn = psycopg.connect(
    os.getenv("DATABASE_URL")
)


def get_all_products():
    with conn.cursor() as cur:

        cur.execute("""
            SELECT
                id,
                name,
                description,
                category,
                "subCategory",
                "articleType",
                gender,
                color,
                season,
                usage,
                image,
                price,
                embedding
            FROM products
        """)

        rows = cur.fetchall()

    products = []

    for row in rows:

        products.append({
            "_id": row[0],
            "name": row[1],
            "description": row[2],
            "category": row[3],
            "subCategory": row[4],
            "articleType": row[5],
            "gender": row[6],
            "color": row[7],
            "season": row[8],
            "usage": row[9],
            "image": row[10],
            "price": float(row[11]),
            "embedding": row[12]
        })

    return products