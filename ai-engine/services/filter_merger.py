from __future__ import annotations

from typing import Any


def _number(
    value: Any,
) -> float | None:
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def merge_filters(
    previous_filters,
    new_filters,
):
    """
    Merge conversational shopping filters.

    - Keep previous values when a new value is None.
    - Replace values explicitly supplied by the latest query.
    - Make "cheaper" and "more expensive" currency-agnostic.
    - Remove temporary parser helper fields.
    """
    previous = dict(
        previous_filters
        if isinstance(
            previous_filters,
            dict,
        )
        else {}
    )

    incoming = dict(
        new_filters
        if isinstance(
            new_filters,
            dict,
        )
        else {}
    )

    merged = dict(previous)

    for key, value in (
        incoming.items()
    ):
        if value is None:
            continue

        merged[key] = value

    price_intent = incoming.get(
        "priceIntent"
    )

    if price_intent == "lower":
        current_max = _number(
            incoming.get(
                "maxPrice"
            )
        )

        if current_max is None:
            current_max = _number(
                previous.get(
                    "maxPrice"
                )
            )

        if current_max is not None:
            merged[
                "maxPrice"
            ] = round(
                max(
                    0.01,
                    current_max
                    * 0.80,
                ),
                2,
            )

    elif price_intent == "higher":
        reference_price = _number(
            incoming.get(
                "maxPrice"
            )
        )

        if reference_price is None:
            reference_price = _number(
                previous.get(
                    "maxPrice"
                )
            )

        if reference_price is not None:
            merged[
                "minPrice"
            ] = reference_price
            merged.pop(
                "maxPrice",
                None,
            )

    merged.pop(
        "priceIntent",
        None,
    )

    return merged
