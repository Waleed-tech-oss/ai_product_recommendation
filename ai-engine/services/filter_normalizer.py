def normalize_filters(filters: dict):

    if not filters:
        return {}

    normalized = filters.copy()

    # ----------------------------------------
    # Product Type Mapping
    # ----------------------------------------

    product_type_map = {

        "snowboard": "snowboard",
        "snowboards": "snowboard",

        "gift card": "gift_card",
        "gift cards": "gift_card",

        "t-shirt": "t-shirt",
        "tshirt": "t-shirt",
        "shirt": "shirt",
        "shirts": "shirt",

        "hoodie": "hoodie",
        "hoodies": "hoodie",

        "cap": "cap",
        "caps": "cap"

    }

    # ----------------------------------------
    # Normalize Product Type
    # ----------------------------------------

    product_type = normalized.get("productType")

    if product_type:

        normalized["productType"] = product_type_map.get(
            product_type.lower(),
            product_type.lower()
        )

    # ----------------------------------------
    # Normalize Vendor
    # ----------------------------------------

    vendor = normalized.get("vendor")

    if vendor:

        normalized["vendor"] = vendor.strip()

    return normalized