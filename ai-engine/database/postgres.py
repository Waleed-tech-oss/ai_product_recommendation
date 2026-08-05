import os
import re
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

_SCHEMA_READY = False


SHOPIFY_COLUMNS = """
    id,
    shopify_id,
    shop_domain,
    title,
    handle,
    vendor,
    product_type,
    description,
    description_html,
    tags,
    collections,
    taxonomy_category_id,
    taxonomy_category_name,
    taxonomy_category_full_name,
    image_url,
    image_alt_text,
    sku,
    price,
    currency_code,
    available_for_sale,
    created_at,
    updated_at,
    image_embedding,
    text_embedding,
    search_document,
    variants,
    embedding
"""


def ensure_shopify_search_schema() -> None:
    """Create the enriched-search columns once per process."""
    global _SCHEMA_READY

    if _SCHEMA_READY:
        return

    statements = [
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS shop_domain TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS description TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS description_html TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS collections JSONB NOT NULL DEFAULT '[]'::jsonb",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS taxonomy_category_id TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS taxonomy_category_name TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS taxonomy_category_full_name TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS image_alt_text TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS currency_code TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS available_for_sale BOOLEAN",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS image_embedding JSONB",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS text_embedding JSONB",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS search_document TEXT",
        "ALTER TABLE shopify_products ADD COLUMN IF NOT EXISTS variants JSONB NOT NULL DEFAULT '[]'::jsonb",
        "UPDATE shopify_products SET image_embedding = embedding WHERE image_embedding IS NULL AND embedding IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_shopify_products_type_lower ON shopify_products (LOWER(product_type))",
        "CREATE INDEX IF NOT EXISTS idx_shopify_products_vendor_lower ON shopify_products (LOWER(vendor))",
        "CREATE INDEX IF NOT EXISTS idx_shopify_products_shop_domain ON shopify_products (shop_domain)",
        "CREATE INDEX IF NOT EXISTS idx_shopify_products_taxonomy_lower ON shopify_products (LOWER(taxonomy_category_full_name))",
    ]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()

        _SCHEMA_READY = True

    except Exception as error:
        print("\n========== SHOPIFY SCHEMA ERROR ==========")
        print(error)
        print("==========================================\n")
        raise


def _json_value(value, default):
    return value if value is not None else default


def map_shopify_product(row) -> dict[str, Any]:
    image_embedding = row[22] or row[26]

    return {
        "id": row[0],
        "shopify_id": row[1],
        "shop_domain": row[2],
        "title": row[3],
        "handle": row[4],
        "vendor": row[5],
        "product_type": row[6],
        "description": row[7],
        "description_html": row[8],
        "tags": _json_value(row[9], []),
        "collections": _json_value(row[10], []),
        "taxonomy_category_id": row[11],
        "taxonomy_category_name": row[12],
        "taxonomy_category_full_name": row[13],
        "image_url": row[14],
        "image_alt_text": row[15],
        "sku": row[16],
        "price": float(row[17]) if row[17] is not None else None,
        "currency_code": row[18],
        "available_for_sale": row[19],
        "created_at": row[20],
        "updated_at": row[21],
        "image_embedding": image_embedding,
        "text_embedding": row[23],
        "search_document": row[24],
        "variants": _json_value(row[25], []),
        # Backward compatibility for existing image-search callers.
        "embedding": image_embedding,
    }


def save_shopify_product(
    shopify_id,
    title,
    handle,
    vendor=None,
    product_type=None,
    image_url=None,
    sku=None,
    price=None,
    embedding=None,
    *,
    shop_domain="",
    description=None,
    description_html=None,
    tags=None,
    collections=None,
    taxonomy_category_id=None,
    taxonomy_category_name=None,
    taxonomy_category_full_name=None,
    image_alt_text=None,
    currency_code=None,
    available_for_sale=None,
    created_at=None,
    updated_at=None,
    image_embedding=None,
    text_embedding=None,
    search_document=None,
    variants=None,
):
    ensure_shopify_search_schema()

    final_image_embedding = image_embedding or embedding

    query = """
        INSERT INTO shopify_products (
            shopify_id,
            shop_domain,
            title,
            handle,
            vendor,
            product_type,
            description,
            description_html,
            tags,
            collections,
            taxonomy_category_id,
            taxonomy_category_name,
            taxonomy_category_full_name,
            image_url,
            image_alt_text,
            sku,
            price,
            currency_code,
            available_for_sale,
            created_at,
            updated_at,
            image_embedding,
            text_embedding,
            search_document,
            variants,
            embedding
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (shopify_id)
        DO UPDATE SET
            shop_domain = EXCLUDED.shop_domain,
            title = EXCLUDED.title,
            handle = EXCLUDED.handle,
            vendor = EXCLUDED.vendor,
            product_type = EXCLUDED.product_type,
            description = EXCLUDED.description,
            description_html = EXCLUDED.description_html,
            tags = EXCLUDED.tags,
            collections = EXCLUDED.collections,
            taxonomy_category_id = EXCLUDED.taxonomy_category_id,
            taxonomy_category_name = EXCLUDED.taxonomy_category_name,
            taxonomy_category_full_name = EXCLUDED.taxonomy_category_full_name,
            image_url = EXCLUDED.image_url,
            image_alt_text = EXCLUDED.image_alt_text,
            sku = EXCLUDED.sku,
            price = EXCLUDED.price,
            currency_code = EXCLUDED.currency_code,
            available_for_sale = EXCLUDED.available_for_sale,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at,
            image_embedding = EXCLUDED.image_embedding,
            text_embedding = EXCLUDED.text_embedding,
            search_document = EXCLUDED.search_document,
            variants = EXCLUDED.variants,
            embedding = EXCLUDED.embedding
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        shopify_id,
                        shop_domain or "",
                        title,
                        handle,
                        vendor,
                        product_type,
                        description,
                        description_html,
                        Jsonb(tags or []),
                        Jsonb(collections or []),
                        taxonomy_category_id,
                        taxonomy_category_name,
                        taxonomy_category_full_name,
                        image_url,
                        image_alt_text,
                        sku,
                        float(price) if price not in (None, "") else None,
                        currency_code,
                        available_for_sale,
                        created_at,
                        updated_at,
                        Jsonb(final_image_embedding) if final_image_embedding else None,
                        Jsonb(text_embedding) if text_embedding else None,
                        search_document,
                        Jsonb(variants or []),
                        Jsonb(final_image_embedding) if final_image_embedding else None,
                    ),
                )
            conn.commit()

    except Exception as error:
        print("\n========== SAVE SHOPIFY PRODUCT ERROR ==========")
        print(error)
        print("================================================\n")
        raise


def _shop_filter_clause(shop_domain, params):
    if not shop_domain:
        return ""

    params.append(shop_domain)
    return " AND shop_domain = %s"


def get_all_shopify_products(shop_domain=None):
    ensure_shopify_search_schema()

    params: list[Any] = []
    query = f"SELECT {SHOPIFY_COLUMNS} FROM shopify_products WHERE 1 = 1"
    query += _shop_filter_clause(shop_domain, params)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        return [map_shopify_product(row) for row in rows]

    except Exception as error:
        print("\n========== GET SHOPIFY PRODUCTS ERROR ==========")
        print(error)
        print("===============================================\n")
        return []


def get_chat_suggestions(query, shop_domain=None):
    ensure_shopify_search_schema()

    params: list[Any] = [f"%{query}%"]
    sql = """
        SELECT DISTINCT title
        FROM shopify_products
        WHERE LOWER(title) LIKE LOWER(%s)
    """
    sql += _shop_filter_clause(shop_domain, params)
    sql += " ORDER BY title LIMIT 5"

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [row[0] for row in rows]

    except Exception as error:
        print("\n========== SUGGESTIONS ERROR ==========")
        print(error)
        print("=======================================\n")
        return []


def get_catalog_vocabulary(shop_domain=None):
    ensure_shopify_search_schema()

    shop_sql = ""
    shop_params: list[Any] = []

    if shop_domain:
        shop_sql = " AND shop_domain = %s"
        shop_params = [shop_domain]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT product_type
                    FROM shopify_products
                    WHERE product_type IS NOT NULL
                      AND TRIM(product_type) <> ''
                      {shop_sql}
                    ORDER BY product_type
                    """,
                    shop_params,
                )
                product_types = [row[0] for row in cur.fetchall()]

                cur.execute(
                    f"""
                    SELECT DISTINCT vendor
                    FROM shopify_products
                    WHERE vendor IS NOT NULL
                      AND TRIM(vendor) <> ''
                      {shop_sql}
                    ORDER BY vendor
                    """,
                    shop_params,
                )
                vendors = [row[0] for row in cur.fetchall()]

                cur.execute(
                    f"""
                    SELECT DISTINCT taxonomy_category_full_name
                    FROM shopify_products
                    WHERE taxonomy_category_full_name IS NOT NULL
                      AND TRIM(taxonomy_category_full_name) <> ''
                      {shop_sql}
                    ORDER BY taxonomy_category_full_name
                    """,
                    shop_params,
                )
                taxonomy_categories = [row[0] for row in cur.fetchall()]

        return {
            "product_types": product_types,
            "vendors": vendors,
            "taxonomy_categories": taxonomy_categories,
            "aliases": {},
        }

    except Exception as error:
        print("\n========== VOCABULARY ERROR ==========")
        print(error)
        print("======================================\n")
        return {
            "product_types": [],
            "vendors": [],
            "taxonomy_categories": [],
            "aliases": {},
        }


def _product_type_variants(value: Any) -> list[str]:
    clean_value = " ".join(str(value or "").strip().lower().split())
    if not clean_value:
        return []

    variants = {clean_value}
    words = clean_value.split()
    last = words[-1]
    prefix = words[:-1]

    if last.endswith("ies") and len(last) > 3:
        variants.add(" ".join(prefix + [f"{last[:-3]}y"]))
    elif last.endswith("es") and last.endswith(("ses", "xes", "zes", "ches", "shes")):
        variants.add(" ".join(prefix + [last[:-2]]))
    elif last.endswith("s") and not last.endswith("ss"):
        variants.add(" ".join(prefix + [last[:-1]]))
    else:
        if last.endswith("y") and len(last) > 1:
            variants.add(" ".join(prefix + [f"{last[:-1]}ies"]))
        elif last.endswith(("s", "x", "z", "ch", "sh")):
            variants.add(" ".join(prefix + [f"{last}es"]))
        else:
            variants.add(" ".join(prefix + [f"{last}s"]))

    return sorted(variants)


def get_filtered_products(filters, limit=200):
    ensure_shopify_search_schema()
    filters = dict(filters or {})

    query = f"SELECT {SHOPIFY_COLUMNS} FROM shopify_products WHERE 1 = 1"
    params: list[Any] = []

    shop_domain = filters.get("shopDomain") or filters.get("shop_domain")
    query += _shop_filter_clause(shop_domain, params)

    product_type = filters.get("productType")
    if product_type:
        variants = _product_type_variants(product_type)
        placeholders = ", ".join(["LOWER(%s)"] * len(variants))
        # Strict catalog guard: a known product type is matched only
        # against canonical product_type, not an arbitrary title word.
        query += f"""
            AND LOWER(COALESCE(product_type, ''))
                IN ({placeholders})
        """
        params.extend(variants)

    handle = filters.get("handle")
    if handle:
        query += """
            AND LOWER(
                COALESCE(
                    handle,
                    ''
                )
            ) = LOWER(%s)
        """
        params.append(handle)

    vendor = filters.get("vendor")
    if vendor:
        query += " AND LOWER(COALESCE(vendor, '')) = LOWER(%s)"
        params.append(vendor)

    taxonomy = filters.get("taxonomyCategory")
    if taxonomy:
        query += " AND LOWER(COALESCE(taxonomy_category_full_name, '')) = LOWER(%s)"
        params.append(taxonomy)

    collection = filters.get("collection")
    if collection:
        query += """
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    COALESCE(
                        collections,
                        '[]'::jsonb
                    )
                ) AS collection_item
                WHERE LOWER(
                    COALESCE(
                        collection_item->>'title',
                        ''
                    )
                ) = LOWER(%s)
            )
        """
        params.append(collection)

    if filters.get("minPrice") is not None:
        query += " AND price >= %s"
        params.append(filters["minPrice"])

    if filters.get("maxPrice") is not None:
        query += " AND price <= %s"
        params.append(filters["maxPrice"])

    if filters.get("availableOnly") is True:
        query += " AND available_for_sale IS TRUE"

    sort = filters.get("sort")
    if sort == "price_low":
        query += " ORDER BY price ASC NULLS LAST"
    elif sort == "price_high":
        query += " ORDER BY price DESC NULLS LAST"
    elif sort == "newest":
        query += " ORDER BY created_at DESC NULLS LAST"

    try:
        safe_limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        safe_limit = 200

    query += " LIMIT %s"
    params.append(safe_limit)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return [map_shopify_product(row) for row in rows]

    except Exception as error:
        print("\n========== SHOPIFY FILTER ERROR ==========")
        print(error)
        print("==========================================\n")
        return []


def get_grouped_products_by_types(
    product_types: list[str],
    base_filters: dict[str, Any] | None = None,
    per_type_limit: int = 50,
) -> list[dict[str, Any]]:
    base_filters = dict(base_filters or {})
    base_filters.pop("productType", None)
    base_filters.pop("productTypes", None)

    groups = []
    seen_types = set()

    for product_type in product_types or []:
        clean_type = " ".join(str(product_type or "").strip().split())
        key = clean_type.lower()
        if not clean_type or key in seen_types:
            continue
        seen_types.add(key)

        filters = dict(base_filters)
        filters["productType"] = clean_type
        products = get_filtered_products(filters, limit=per_type_limit)
        groups.append({"productType": clean_type, "products": products})

    return groups


def get_product_type_facets(product_type: str, shop_domain=None) -> list[dict[str, Any]]:
    """Return dynamic taxonomy/collection facets for a broad type."""
    ensure_shopify_search_schema()

    params: list[Any] = [product_type]
    shop_clause = _shop_filter_clause(shop_domain, params)

    query = f"""
        SELECT
            taxonomy_category_full_name,
            collections,
            COUNT(*)
        FROM shopify_products
        WHERE LOWER(COALESCE(product_type, '')) = LOWER(%s)
          {shop_clause}
        GROUP BY taxonomy_category_full_name, collections
        ORDER BY COUNT(*) DESC
        LIMIT 30
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        facets: dict[str, dict[str, Any]] = {}

        for taxonomy_name, collections, count in rows:
            if taxonomy_name:
                key = f"taxonomy:{taxonomy_name.lower()}"
                facets[key] = {
                    "type": "taxonomy",
                    "label": taxonomy_name,
                    "value": taxonomy_name,
                    "count": facets.get(key, {}).get("count", 0) + count,
                }

            for collection in collections or []:
                title = collection.get("title") if isinstance(collection, dict) else str(collection)
                if not title:
                    continue
                key = f"collection:{title.lower()}"
                facets[key] = {
                    "type": "collection",
                    "label": title,
                    "value": title,
                    "count": facets.get(key, {}).get("count", 0) + count,
                }

        return sorted(facets.values(), key=lambda item: item["count"], reverse=True)[:8]

    except Exception as error:
        print("\n========== PRODUCT FACETS ERROR ==========")
        print(error)
        print("=========================================\n")
        return []
def get_product_type_profile(
    product_type: str,
    shop_domain: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """
    Build a broad-category profile from the store's real product
    taxonomy and collections. Product/category names are never
    hardcoded.
    """
    filters: dict[str, Any] = {
        "productType": product_type,
    }

    if shop_domain:
        filters["shopDomain"] = shop_domain

    products = get_filtered_products(
        filters,
        limit=limit,
    )

    def _profile_tokens(
        value: Any,
    ) -> set[str]:
        raw_tokens = re.findall(
            r"[a-z0-9]+",
            str(value or "").lower(),
        )

        normalized: set[str] = set()

        for token in raw_tokens:
            if (
                token.endswith("ies")
                and len(token) > 3
            ):
                token = (
                    token[:-3]
                    + "y"
                )
            elif (
                token.endswith("es")
                and token.endswith(
                    (
                        "ses",
                        "xes",
                        "zes",
                        "ches",
                        "shes",
                    )
                )
            ):
                token = token[:-2]
            elif (
                token.endswith("s")
                and not token.endswith(
                    "ss"
                )
            ):
                token = token[:-1]

            if token:
                normalized.add(
                    token
                )

        return normalized

    product_type_tokens = (
        _profile_tokens(
            product_type
        )
    )

    title_match_count = 0
    title_mismatch_count = 0

    facet_products: dict[
        tuple[str, str],
        set[str],
    ] = {}

    facet_values: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for product in products:
        product_key = str(
            product.get("shopify_id")
            or product.get("id")
        )

        title_tokens = (
            _profile_tokens(
                product.get(
                    "title"
                )
            )
        )

        if (
            product_type_tokens
            and title_tokens
            and (
                product_type_tokens
                .issubset(
                    title_tokens
                )
                or title_tokens
                .issubset(
                    product_type_tokens
                )
            )
        ):
            title_match_count += 1
        else:
            title_mismatch_count += 1

        taxonomy = " ".join(
            str(
                product.get(
                    "taxonomy_category_full_name"
                )
                or ""
            )
            .strip()
            .split()
        )

        if taxonomy:
            key = (
                "taxonomy",
                taxonomy.lower(),
            )
            facet_products.setdefault(
                key,
                set(),
            ).add(product_key)
            facet_values[key] = {
                "type": "taxonomy",
                "label": taxonomy,
                "value": taxonomy,
            }

        for collection in (
            product.get("collections")
            or []
        ):
            if isinstance(
                collection,
                dict,
            ):
                title = " ".join(
                    str(
                        collection.get(
                            "title"
                        )
                        or ""
                    )
                    .strip()
                    .split()
                )
            else:
                title = " ".join(
                    str(collection)
                    .strip()
                    .split()
                )

            if not title:
                continue

            key = (
                "collection",
                title.lower(),
            )
            facet_products.setdefault(
                key,
                set(),
            ).add(product_key)
            facet_values[key] = {
                "type": "collection",
                "label": title,
                "value": title,
            }

    facets = [
        {
            **facet_values[key],
            "count": len(
                facet_products[key]
            ),
        }
        for key in facet_values
    ]

    facets.sort(
        key=lambda item: (
            -int(
                item.get("count")
                or 0
            ),
            (
                0
                if item.get("type")
                == "taxonomy"
                else 1
            ),
            str(
                item.get("label")
                or ""
            ).lower(),
        )
    )

    fallback_facet_mode = None

    # Some merchant products have a broad product_type but no Shopify
    # taxonomy or collections. In that case, build deterministic
    # product-title refinement options from the real catalog instead
    # of silently returning a weakly classified product.
    if not facets:
        seen_handles: set[str] = set()

        for product in products:
            title = " ".join(
                str(
                    product.get("title")
                    or ""
                )
                .strip()
                .split()
            )
            handle = " ".join(
                str(
                    product.get("handle")
                    or ""
                )
                .strip()
                .split()
            )

            handle_key = handle.lower()

            if (
                not title
                or not handle
                or handle_key
                in seen_handles
            ):
                continue

            seen_handles.add(
                handle_key
            )

            facets.append({
                "type": "product",
                "label": title,
                "value": handle,
                "count": 1,
            })

        if facets:
            fallback_facet_mode = (
                "product_title"
            )

    title_evaluated_count = (
        title_match_count
        + title_mismatch_count
    )

    title_match_ratio = (
        title_match_count
        / title_evaluated_count
        if title_evaluated_count
        else 0.0
    )

    return {
        "productType": product_type,
        "productCount": len(products),
        "titleMatchCount": (
            title_match_count
        ),
        "titleMismatchCount": (
            title_mismatch_count
        ),
        "titleMatchRatio": round(
            title_match_ratio,
            4,
        ),
        "taxonomyFacetCount": len([
            facet
            for facet in facets
            if facet.get("type")
            == "taxonomy"
        ]),
        "collectionFacetCount": len([
            facet
            for facet in facets
            if facet.get("type")
            == "collection"
        ]),
        "productFacetCount": len([
            facet
            for facet in facets
            if facet.get("type")
            == "product"
        ]),
        "fallbackFacetMode": (
            fallback_facet_mode
        ),
        "facets": facets,
    }
