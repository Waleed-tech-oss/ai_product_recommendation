from __future__ import annotations

import os
import re
import warnings
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_BYTES = int(
    os.getenv(
        "MAX_IMAGE_UPLOAD_BYTES",
        str(8 * 1024 * 1024),
    )
)

MAX_IMAGE_PIXELS = int(
    os.getenv(
        "MAX_IMAGE_PIXELS",
        "25000000",
    )
)

GENERIC_VISUAL_WORDS = {
    "a",
    "an",
    "and",
    "aur",
    "above",
    "below",
    "dikha",
    "dikhao",
    "find",
    "for",
    "image",
    "is",
    "isjaisa",
    "isjaisi",
    "iss",
    "jaisa",
    "jaisi",
    "jese",
    "jesa",
    "like",
    "me",
    "mujhe",
    "mujhy",
    "mjy",
    "of",
    "product",
    "products",
    "same",
    "show",
    "similar",
    "this",
    "under",
    "with",
}

PRICE_ONLY_WORDS = {
    "cheap",
    "cheaper",
    "cheapest",
    "expensive",
    "higher",
    "lower",
    "price",
    "sasta",
    "sasti",
    "saste",
    "mehnga",
    "mehngi",
    "mehnge",
    "kam",
    "zyada",
}


class ImageValidationError(ValueError):
    pass


def validate_image_bytes(
    content: bytes,
    content_type: str | None,
) -> dict[str, Any]:
    """
    Validate MIME type, byte size, actual image format, and
    decoded image dimensions.
    """
    if not content:
        raise ImageValidationError(
            "The uploaded image is empty."
        )

    if len(content) > MAX_IMAGE_BYTES:
        max_mb = round(
            MAX_IMAGE_BYTES
            / (1024 * 1024),
            1,
        )

        raise ImageValidationError(
            f"Image is too large. Maximum size is {max_mb} MB."
        )

    if (
        content_type
        and content_type.lower()
        not in ALLOWED_IMAGE_TYPES
    ):
        raise ImageValidationError(
            "Only JPG, PNG, and WEBP images are supported."
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            image = Image.open(
                BytesIO(content)
            )
            image.verify()

            image = Image.open(
                BytesIO(content)
            )
            width, height = image.size
            image_format = (
                image.format or ""
            ).upper()
            image.close()

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as error:
        raise ImageValidationError(
            "The uploaded file is not a valid supported image."
        ) from error

    if (
        width <= 0
        or height <= 0
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise ImageValidationError(
            "The image dimensions are too large."
        )

    if image_format not in {
        "JPEG",
        "PNG",
        "WEBP",
    }:
        raise ImageValidationError(
            "Only JPG, PNG, and WEBP images are supported."
        )

    return {
        "width": width,
        "height": height,
        "format": image_format,
        "bytes": len(content),
    }


def has_meaningful_visual_text(
    original_message: str,
    semantic_query: str,
) -> bool:
    """
    Decide whether text should contribute to CLIP hybrid ranking.

    Price-only instructions are applied as database filters and should
    not dilute image similarity. Descriptive terms such as "black",
    "winter", "shoe", or a vendor name do contribute.
    """
    source = (
        semantic_query
        or original_message
        or ""
    ).lower()

    tokens = re.findall(
        r"[a-zA-Z]+",
        source,
    )

    meaningful_tokens = [
        token
        for token in tokens
        if token
        not in GENERIC_VISUAL_WORDS
        and token
        not in PRICE_ONLY_WORDS
    ]

    return bool(
        meaningful_tokens
    )


def visual_result_is_low_confidence(
    recommendations: list[dict[str, Any]],
) -> bool:
    if not recommendations:
        return True

    top_score = recommendations[0].get(
        "score"
    )

    if not isinstance(
        top_score,
        (int, float),
    ):
        return False

    try:
        threshold = float(
            os.getenv(
                "MIN_VISUAL_SCORE",
                "0.20",
            )
        )
    except ValueError:
        threshold = 0.20

    threshold = max(
        0.0,
        min(threshold, 1.0),
    )

    return float(top_score) < threshold


def build_visual_confidence_response(
    response_language: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    roman_urdu = (
        response_language
        == "roman_urdu"
    )

    return {
        "intent": "clarification",
        "clarificationType": (
            "low_visual_confidence"
        ),
        "responseLanguage": (
            response_language
        ),
        "filters": filters,
        "message": (
            (
                "Image ka catalog products ke saath strong match "
                "nahi mila. Clear product image upload karein ya "
                "product type, brand, color, ya budget bhi likhein."
            )
            if roman_urdu
            else (
                "The image did not strongly match the catalog. "
                "Upload a clearer product image or add a product "
                "type, brand, color, or budget."
            )
        ),
        "options": [],
        "recommendedProducts": [],
    }
