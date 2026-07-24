def merge_filters(previous_filters, new_filters):
    """
    Merge previous shopping filters with newly extracted filters.

    Features:
    - Keep previous values if new value is None
    - Replace old values with new ones
    - Handle conversational price updates
    - Remove temporary helper fields
    """

    if previous_filters is None:
        previous_filters = {}

    merged = previous_filters.copy()

    # ------------------------------------
    # Normal Merge
    # ------------------------------------

    for key, value in new_filters.items():

        if value is None:
            continue

        merged[key] = value

    # ------------------------------------
    # Handle Price Intent
    # ------------------------------------

    price_intent = merged.get("priceIntent")

    if price_intent == "lower":

        current_max = merged.get("maxPrice")

        if current_max:
            merged["maxPrice"] = max(
                500,
                int(current_max * 0.8)
            )

    elif price_intent == "higher":

        current_max = merged.get("maxPrice")

        if current_max:
            merged["minPrice"] = current_max
            merged.pop("maxPrice", None)

    # ------------------------------------
    # Remove Temporary Field
    # ------------------------------------

    merged.pop("priceIntent", None)

    return merged