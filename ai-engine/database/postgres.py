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

def get_filtered_products(filters):

    query = """
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
        WHERE 1=1
    """

    params = []

    if filters.get("category"):
        query += " AND LOWER(category) = LOWER(%s)"
        params.append(filters["category"])

    if filters.get("subCategory"):
        query += ' AND LOWER("subCategory") = LOWER(%s)'
        params.append(filters["subCategory"])

    if filters.get("articleType"):
        query += ' AND LOWER("articleType") = LOWER(%s)'
        params.append(filters["articleType"])

    if filters.get("gender"):
        query += " AND LOWER(gender) = LOWER(%s)"
        params.append(filters["gender"])

    if filters.get("color"):
        query += " AND LOWER(color) = LOWER(%s)"
        params.append(filters["color"])

    if filters.get("season"):
        query += " AND LOWER(season) = LOWER(%s)"
        params.append(filters["season"])

    if filters.get("usage"):
        query += " AND LOWER(usage) = LOWER(%s)"
        params.append(filters["usage"])

    if filters.get("maxPrice") is not None:
        query += " AND price <= %s"
        params.append(filters["maxPrice"])

    if filters.get("minPrice") is not None:
        query += " AND price >= %s"
        params.append(filters["minPrice"])

    with conn.cursor() as cur:

        cur.execute(query, params)

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