def merge_filters(previous_filters, new_filters):
    """
    Merge previous shopping filters with newly extracted filters.

    Rules:
    - Keep previous values if new value is None.
    - Replace previous value if user provides a new one.
    - Add completely new fields.
    """

    if previous_filters is None:
        previous_filters = {}

    merged = previous_filters.copy()

    for key, value in new_filters.items():

        if value is None:
            continue

        merged[key] = value

    return merged