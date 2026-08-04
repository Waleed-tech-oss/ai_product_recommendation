import os
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


load_dotenv()


def get_connection():
    return psycopg.connect(
        os.getenv(
            "DATABASE_URL"
        )
    )


# =========================================================
# LEGACY DATASET PRODUCTS
# =========================================================

def map_product(
    row,
) -> dict[str, Any]:
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
        "price": (
            float(row[11])
            if row[11]
            is not None
            else None
        ),
        "embedding": row[12],
    }


def get_all_products():
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
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

        return [
            map_product(row)
            for row in rows
        ]

    except Exception as error:
        print(
            "\n========== DATABASE ERROR =========="
        )
        print(error)
        print(
            "====================================\n"
        )
        return []


def get_product_by_id(
    product_id,
):
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
        WHERE id = %s
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (product_id,),
                )
                row = cur.fetchone()

        return (
            map_product(row)
            if row
            else None
        )

    except Exception as error:
        print(
            "\n========== GET PRODUCT ERROR =========="
        )
        print(error)
        print(
            "=======================================\n"
        )
        return None


def get_similar_candidate_products(
    category,
    article_type,
    gender=None,
):
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
        WHERE LOWER(category) = LOWER(%s)
          AND LOWER("articleType") = LOWER(%s)
    """

    params: list[Any] = [
        category,
        article_type,
    ]

    if gender:
        query += (
            " AND LOWER(gender) = LOWER(%s)"
        )
        params.append(gender)

    query += " LIMIT 500"

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    params,
                )
                rows = cur.fetchall()

        return [
            map_product(row)
            for row in rows
        ]

    except Exception as error:
        print(
            "\n========== CANDIDATE QUERY ERROR =========="
        )
        print(error)
        print(
            "===========================================\n"
        )
        return []


# =========================================================
# SHOPIFY PRODUCTS
# =========================================================

def map_shopify_product(
    row,
) -> dict[str, Any]:
    return {
        "id": row[0],
        "shopify_id": row[1],
        "title": row[2],
        "handle": row[3],
        "vendor": row[4],
        "product_type": row[5],
        "image_url": row[6],
        "sku": row[7],
        "price": (
            float(row[8])
            if row[8]
            is not None
            else None
        ),
        "embedding": row[9],
    }


def save_shopify_product(
    shopify_id,
    title,
    handle,
    vendor,
    product_type,
    image_url,
    sku,
    price,
    embedding,
):
    query = """
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
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (shopify_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            handle = EXCLUDED.handle,
            vendor = EXCLUDED.vendor,
            product_type = EXCLUDED.product_type,
            image_url = EXCLUDED.image_url,
            sku = EXCLUDED.sku,
            price = EXCLUDED.price,
            embedding = EXCLUDED.embedding
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        shopify_id,
                        title,
                        handle,
                        vendor,
                        product_type,
                        image_url,
                        sku,
                        (
                            float(price)
                            if price
                            is not None
                            else None
                        ),
                        Jsonb(
                            embedding
                        ),
                    ),
                )

            conn.commit()

    except Exception as error:
        print(
            "\n========== SAVE SHOPIFY PRODUCT ERROR =========="
        )
        print(error)
        print(
            "================================================\n"
        )


def get_all_shopify_products():
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
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

        return [
            map_shopify_product(
                row
            )
            for row in rows
        ]

    except Exception as error:
        print(
            "\n========== GET SHOPIFY PRODUCTS ERROR =========="
        )
        print(error)
        print(
            "===============================================\n"
        )
        return []


def get_chat_suggestions(
    query,
):
    sql = """
        SELECT DISTINCT title
        FROM shopify_products
        WHERE LOWER(title) LIKE LOWER(%s)
        ORDER BY title
        LIMIT 5
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        f"%{query}%",
                    ),
                )
                rows = cur.fetchall()

        return [
            row[0]
            for row in rows
        ]

    except Exception as error:
        print(
            "\n========== SUGGESTIONS ERROR =========="
        )
        print(error)
        print(
            "=======================================\n"
        )
        return []


def get_catalog_vocabulary():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT product_type
                    FROM shopify_products
                    WHERE product_type IS NOT NULL
                      AND TRIM(product_type) <> ''
                    ORDER BY product_type
                    """
                )

                product_types = [
                    row[0]
                    for row
                    in cur.fetchall()
                ]

                cur.execute(
                    """
                    SELECT DISTINCT vendor
                    FROM shopify_products
                    WHERE vendor IS NOT NULL
                      AND TRIM(vendor) <> ''
                    ORDER BY vendor
                    """
                )

                vendors = [
                    row[0]
                    for row
                    in cur.fetchall()
                ]

        return {
            "product_types": (
                product_types
            ),
            "vendors": vendors,
        }

    except Exception as error:
        print(
            "\n========== VOCABULARY ERROR =========="
        )
        print(error)
        print(
            "======================================\n"
        )

        return {
            "product_types": [],
            "vendors": [],
        }


def _product_type_variants(
    value: Any,
) -> list[str]:
    clean_value = " ".join(
        str(value or "")
        .strip()
        .lower()
        .split()
    )

    if not clean_value:
        return []

    variants = {
        clean_value,
    }

    if clean_value.endswith(
        "ies"
    ) and len(clean_value) > 3:
        variants.add(
            f"{clean_value[:-3]}y"
        )

    elif clean_value.endswith(
        "es"
    ) and clean_value.endswith(
        (
            "ses",
            "xes",
            "zes",
            "ches",
            "shes",
        )
    ):
        variants.add(
            clean_value[:-2]
        )

    elif (
        clean_value.endswith("s")
        and not clean_value.endswith(
            "ss"
        )
    ):
        variants.add(
            clean_value[:-1]
        )

    else:
        if clean_value.endswith(
            "y"
        ) and len(clean_value) > 1:
            variants.add(
                f"{clean_value[:-1]}ies"
            )

        elif clean_value.endswith(
            (
                "s",
                "x",
                "z",
                "ch",
                "sh",
            )
        ):
            variants.add(
                f"{clean_value}es"
            )

        else:
            variants.add(
                f"{clean_value}s"
            )

    return sorted(
        variants
    )


def get_filtered_products(
    filters,
    limit=200,
):
    filters = dict(
        filters or {}
    )

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
        WHERE 1 = 1
    """

    params: list[Any] = []

    product_type = filters.get(
        "productType"
    )

    if product_type:
        variants = (
            _product_type_variants(
                product_type
            )
        )

        exact_placeholders = (
            ", ".join(
                ["LOWER(%s)"]
                * len(variants)
            )
        )

        title_conditions = (
            " OR ".join(
                [
                    (
                        "LOWER(COALESCE(title, '')) "
                        "LIKE LOWER(%s)"
                    )
                    for _ in variants
                ]
            )
        )

        query += f"""
            AND (
                LOWER(
                    COALESCE(
                        product_type,
                        ''
                    )
                ) IN ({exact_placeholders})
                OR {title_conditions}
            )
        """

        params.extend(
            variants
        )

        params.extend(
            [
                f"%{variant}%"
                for variant
                in variants
            ]
        )

    vendor = filters.get(
        "vendor"
    )

    if vendor:
        query += """
            AND LOWER(
                COALESCE(
                    vendor,
                    ''
                )
            ) = LOWER(%s)
        """
        params.append(vendor)

    if (
        filters.get("minPrice")
        is not None
    ):
        query += (
            " AND price >= %s"
        )
        params.append(
            filters["minPrice"]
        )

    if (
        filters.get("maxPrice")
        is not None
    ):
        query += (
            " AND price <= %s"
        )
        params.append(
            filters["maxPrice"]
        )

    sort = filters.get(
        "sort"
    )

    if sort == "price_low":
        query += (
            " ORDER BY price ASC "
            "NULLS LAST"
        )

    elif sort == "price_high":
        query += (
            " ORDER BY price DESC "
            "NULLS LAST"
        )

    try:
        safe_limit = int(
            limit
        )
    except (
        TypeError,
        ValueError,
    ):
        safe_limit = 200

    safe_limit = max(
        1,
        min(
            safe_limit,
            200,
        ),
    )

    query += " LIMIT %s"
    params.append(
        safe_limit
    )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    params,
                )
                rows = cur.fetchall()

        return [
            map_shopify_product(
                row
            )
            for row in rows
        ]

    except Exception as error:
        print(
            "\n========== SHOPIFY FILTER ERROR =========="
        )
        print(error)
        print(
            "==========================================\n"
        )
        return []


def get_grouped_products_by_types(
    product_types: list[str],
    base_filters: (
        dict[str, Any]
        | None
    ) = None,
    per_type_limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Strictly search each requested category separately.

    CLIP is never given the full catalog for a clear category-list
    request.
    """
    base_filters = dict(
        base_filters or {}
    )

    base_filters.pop(
        "productType",
        None,
    )
    base_filters.pop(
        "productTypes",
        None,
    )

    groups: list[
        dict[str, Any]
    ] = []

    seen_types: set[str] = set()

    for product_type in (
        product_types or []
    ):
        clean_type = " ".join(
            str(product_type or "")
            .strip()
            .split()
        )

        type_key = (
            clean_type.lower()
        )

        if (
            not clean_type
            or type_key
            in seen_types
        ):
            continue

        seen_types.add(
            type_key
        )

        filters = dict(
            base_filters
        )
        filters[
            "productType"
        ] = clean_type

        products = (
            get_filtered_products(
                filters=filters,
                limit=per_type_limit,
            )
        )

        groups.append({
            "productType": (
                clean_type
            ),
            "products": products,
        })

    return groups
