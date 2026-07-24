def normalize_filters(filters: dict):

    if not filters:
        return {}

    normalized = filters.copy()

    # ----------------------------
    # Category Mapping
    # ----------------------------
    category_map = {
        "shoe": "Footwear",
        "shoes": "Footwear",
        "footwear": "Footwear",

        "shirt": "Apparel",
        "shirts": "Apparel",
        "tshirt": "Apparel",
        "t-shirt": "Apparel",
        "jeans": "Apparel",
        "pants": "Apparel",
        "trousers": "Apparel",
        "clothing": "Apparel",
        "apparel": "Apparel",

        "watch": "Accessories",
        "watches": "Accessories",

        "bag": "Accessories",
        "bags": "Accessories"
    }

    # ----------------------------
    # SubCategory Mapping
    # ----------------------------
    subcategory_map = {

        "sports shoes": "Shoes",
        "running shoes": "Shoes",
        "casual shoes": "Shoes",
        "formal shoes": "Shoes",
        "shoe": "Shoes",
        "shoes": "Shoes",

        "jeans": "Bottomwear",
        "pants": "Bottomwear",
        "trousers": "Bottomwear",

        "shirt": "Topwear",
        "shirts": "Topwear",
        "tshirt": "Topwear",
        "t-shirt": "Topwear"
    }

    # ----------------------------
    # Article Type Mapping
    # ----------------------------
    article_map = {

        "sports shoes": "Sports Shoes",
        "running shoes": "Sports Shoes",

        "casual shoes": "Casual Shoes",

        "formal shoes": "Formal Shoes",

        "jeans": "Jeans",

        "shirt": "Shirts",
        "shirts": "Shirts",

        "tshirt": "Tshirts",
        "t-shirt": "Tshirts"
    }

    # ----------------------------
    # Normalize Category
    # ----------------------------
    category = normalized.get("category")

    if category:
        normalized["category"] = category_map.get(
            category.lower(),
            category
        )

    # ----------------------------
    # Normalize SubCategory
    # ----------------------------
    sub = normalized.get("subCategory")

    if sub:
        normalized["subCategory"] = subcategory_map.get(
            sub.lower(),
            sub
        )

    # ----------------------------
    # Normalize Article Type
    # ----------------------------
    article = normalized.get("articleType")

    if article:
        normalized["articleType"] = article_map.get(
            article.lower(),
            article
        )

    # ----------------------------
    # Normalize Gender
    # ----------------------------
    gender = normalized.get("gender")

    if gender:
        normalized["gender"] = gender.title()

    # ----------------------------
    # Normalize Color
    # ----------------------------
    color = normalized.get("color")

    if color:
        normalized["color"] = color.title()

    # ----------------------------
    # Normalize Season
    # ----------------------------
    season = normalized.get("season")

    if season:
        normalized["season"] = season.title()

    # ----------------------------
    # Normalize Usage
    # ----------------------------
    usage = normalized.get("usage")

    if usage:
        normalized["usage"] = usage.title()

    return normalized