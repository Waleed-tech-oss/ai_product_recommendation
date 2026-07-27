import os
import psycopg

from dotenv import load_dotenv

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

    # ----------------------------------------
    # Category
    # ----------------------------------------

    if filters.get("category"):
        query += " AND LOWER(category)=LOWER(%s)"
        params.append(filters["category"])

    # ----------------------------------------
    # Sub Category
    # ----------------------------------------

    # if filters.get("subCategory"):
    #     query += ' AND LOWER("subCategory")=LOWER(%s)'
    #     params.append(filters["subCategory"])

    # ----------------------------------------
    # Article Type
    # ----------------------------------------

    if filters.get("articleType"):
        query += ' AND LOWER("articleType")=LOWER(%s)'
        params.append(filters["articleType"])

    # ----------------------------------------
    # Gender
    # ----------------------------------------

    if filters.get("gender"):
        query += " AND LOWER(gender)=LOWER(%s)"
        params.append(filters["gender"])

    # ----------------------------------------
    # Color
    # ----------------------------------------

    if filters.get("color"):
        query += " AND LOWER(color)=LOWER(%s)"
        params.append(filters["color"])

    # ----------------------------------------
    # Season
    # ----------------------------------------

    if filters.get("season"):
        query += " AND LOWER(season)=LOWER(%s)"
        params.append(filters["season"])

    # ----------------------------------------
    # Usage
    # ----------------------------------------

    if filters.get("usage"):
        query += " AND LOWER(usage)=LOWER(%s)"
        params.append(filters["usage"])

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
    # Sorting (Future Ready)
    # ----------------------------------------

    sort = filters.get("sort")

    if sort == "price_low":
        query += " ORDER BY price ASC"

    elif sort == "price_high":
        query += " ORDER BY price DESC"

    # ----------------------------------------
    # Limit Results
    # ----------------------------------------

    query += " LIMIT 200"

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            cur.execute(query, params)

            rows = cur.fetchall()

        conn.close()

        return [map_product(row) for row in rows]

    except Exception as e:

        print("\n========== FILTER QUERY ERROR ==========")
        print(e)
        print("========================================\n")

        return []