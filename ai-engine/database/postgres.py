import os
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb
load_dotenv()


# ----------------------------------------
# Database Connection
# ----------------------------------------

def get_connection():
    return psycopg.connect(
        os.getenv("DATABASE_URL")
    )


# ----------------------------------------
# Product Mapper
# ----------------------------------------

def map_product(row):

    return {
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
    }


# ----------------------------------------
# Get All Products
# ----------------------------------------

def get_all_products():

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
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
                """
            )

            rows = cur.fetchall()

        conn.close()

        return [map_product(row) for row in rows]

    except Exception as e:

        print("\n========== DATABASE ERROR ==========")
        print(e)
        print("====================================\n")

        return []


# ----------------------------------------
# Get Product By ID
# ----------------------------------------

def get_product_by_id(product_id):

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
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
                WHERE id = %s
                """,
                (product_id,)
            )

            row = cur.fetchone()

        conn.close()

        if row:
            return map_product(row)

        return None

    except Exception as e:

        print("\n========== GET PRODUCT ERROR ==========")
        print(e)
        print("=======================================\n")

        return None        


# ----------------------------------------
# Get Similar Candidate Products
# ----------------------------------------

def get_similar_candidate_products(category, article_type, gender=None):

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
        WHERE
            LOWER(category)=LOWER(%s)
            AND LOWER("articleType")=LOWER(%s)
    """

    params = [category, article_type]

    if gender:
        query += " AND LOWER(gender)=LOWER(%s)"
        params.append(gender)

    query += " LIMIT 500"

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(query, params)

            rows = cur.fetchall()

        conn.close()

        return [map_product(row) for row in rows]

    except Exception as e:

        print("\n========== CANDIDATE QUERY ERROR ==========")
        print(e)
        print("===========================================\n")

        return []



# ----------------------------------------
# Get Filtered Products
# ----------------------------------------

def get_filtered_products(filters):

    query = """
        SELECT
            id,
            shopify_id,
            title,
            handle,
            vendor,
            product_type,
            image_url,
            sku,
            price,
            embedding
        FROM shopify_products
        WHERE 1=1
    """

    params = []

   # ----------------------------------------
# Product Type / Title Search
# ----------------------------------------

    if filters.get("productType"):

     query += """
        AND (
            LOWER(COALESCE(product_type, '')) = LOWER(%s)
            OR LOWER(title) LIKE LOWER(%s)
        )
    """

    params.append(filters["productType"])
    params.append(f"%{filters['productType']}%")
    # ----------------------------------------
    # Vendor
    # ----------------------------------------

    if filters.get("vendor"):
        query += """
            AND LOWER(vendor)=LOWER(%s)
        """
        params.append(filters["vendor"])

    # ----------------------------------------
    # Minimum Price
    # ----------------------------------------

    if filters.get("minPrice") is not None:
        query += " AND price >= %s"
        params.append(filters["minPrice"])

    # ----------------------------------------
    # Maximum Price
    # ----------------------------------------

    if filters.get("maxPrice") is not None:
        query += " AND price <= %s"
        params.append(filters["maxPrice"])

    # ----------------------------------------
    # Sorting
    # ----------------------------------------

    sort = filters.get("sort")

    if sort == "price_low":
        query += " ORDER BY price ASC"

    elif sort == "price_high":
        query += " ORDER BY price DESC"

    # ----------------------------------------
    # Limit
    # ----------------------------------------

    query += " LIMIT 200"

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(query, params)

            rows = cur.fetchall()

        conn.close()

        return [
            map_shopify_product(row)
            for row in rows
        ]

    except Exception as e:

        print("\n========== SHOPIFY FILTER ERROR ==========")
        print(e)
        print("==========================================\n")

        return []


# ----------------------------------------
# Save Shopify Product
# ----------------------------------------

def save_shopify_product(
    shopify_id,
    title,
    handle,
    vendor,
    product_type,
    image_url,
    sku,
    price,
    embedding
):

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO shopify_products (

                    shopify_id,
                    title,
                    handle,
                    vendor,
                    product_type,
                    image_url,
                    sku,
                    price,
                    embedding

                )

                VALUES (

                   %s,
                   %s,
                   %s,
                   %s,
                   %s,
                   %s,
                   %s,
                   %s,
                   %s

                )

                ON CONFLICT (shopify_id)

                DO UPDATE SET

                    title=EXCLUDED.title,
                    handle=EXCLUDED.handle,
                    vendor=EXCLUDED.vendor,
                    product_type=EXCLUDED.product_type,
                    image_url=EXCLUDED.image_url,
                    sku=EXCLUDED.sku,
                    price=EXCLUDED.price,
                    embedding=EXCLUDED.embedding

                """,

                (
                    shopify_id,
                    title,
                    handle,
                    vendor,
                    product_type,
                    image_url,
                    sku,
                    float(price) if price else None,
                    Jsonb(embedding)
                )

            )

        conn.commit()

        conn.close()

    except Exception as e:

        print("\n========== SAVE SHOPIFY PRODUCT ERROR ==========")
        print(e)
        print("===============================================\n")




# ----------------------------------------
# Shopify Product Mapper
# ----------------------------------------

def map_shopify_product(row):

    return {
        "id": row[0],
        "shopify_id": row[1],
        "title": row[2],
        "handle": row[3],
        "vendor": row[4],
        "product_type": row[5],
        "image_url": row[6],
        "sku": row[7],
        "price": float(row[8]) if row[8] else None,
        "embedding": row[9]
    }



# ----------------------------------------
# Get All Shopify Products
# ----------------------------------------

def get_all_shopify_products():

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    shopify_id,
                    title,
                    handle,
                    vendor,
                    product_type,
                    image_url,
                    sku,
                    price,
                    embedding
                FROM shopify_products
                """
            )

            rows = cur.fetchall()

        conn.close()

        return [map_shopify_product(row) for row in rows]

    except Exception as e:

        print("\n========== GET SHOPIFY PRODUCTS ERROR ==========")
        print(e)
        print("===============================================\n")

        return []    






def get_chat_suggestions(query):

    conn = get_connection()
    cur = conn.cursor()

    sql = """
        SELECT DISTINCT title
        FROM shopify_products
        WHERE LOWER(title) LIKE LOWER(%s)
        ORDER BY title
        LIMIT 5;
    """

    cur.execute(sql, (f"%{query}%",))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [row[0] for row in rows]