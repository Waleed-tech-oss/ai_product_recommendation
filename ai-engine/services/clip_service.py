from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


MODEL_NAME = "openai/clip-vit-base-patch32"

device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Using Device: {device}")

model = CLIPModel.from_pretrained(MODEL_NAME)
processor = CLIPProcessor.from_pretrained(MODEL_NAME)

model.to(device)
model.eval()

print("✅ CLIP Loaded Successfully")


ImageSource = (
    str
    | Path
    | bytes
    | bytearray
    | BinaryIO
    | Image.Image
)


def normalize_embedding(
    embedding: torch.Tensor,
) -> list[float]:
    """
    L2-normalize a batch containing one embedding and return
    a JSON-serializable Python list.
    """
    if embedding.ndim == 1:
        embedding = embedding.unsqueeze(0)

    norm = embedding.norm(
        dim=-1,
        keepdim=True,
    ).clamp_min(1e-12)

    normalized = embedding / norm

    return (
        normalized
        .squeeze(0)
        .detach()
        .cpu()
        .float()
        .numpy()
        .tolist()
    )


def _open_rgb_image(
    image_source: ImageSource,
) -> Image.Image:
    """
    Open an image from a path, byte sequence, file-like object,
    or an existing PIL image.
    """
    if isinstance(image_source, Image.Image):
        return image_source.convert("RGB")

    if isinstance(
        image_source,
        (bytes, bytearray),
    ):
        return Image.open(
            BytesIO(image_source)
        ).convert("RGB")

    return Image.open(
        image_source
    ).convert("RGB")


def _extract_feature_tensor(
    output,
) -> torch.Tensor:
    """
    Transformers versions have returned either a tensor or an
    output object from CLIP helper methods. Handle both safely.
    """
    if isinstance(output, torch.Tensor):
        return output

    for attribute in (
        "image_embeds",
        "text_embeds",
        "pooler_output",
    ):
        value = getattr(
            output,
            attribute,
            None,
        )

        if isinstance(value, torch.Tensor):
            return value

    raise TypeError(
        "CLIP did not return a supported feature tensor."
    )


def generate_image_embedding(
    image_source: ImageSource,
) -> list[float]:
    """
    Generate a normalized CLIP image embedding.

    Backward compatible:
        generate_image_embedding("uploads/item.jpg")

    New:
        generate_image_embedding(image_bytes)
    """
    image = _open_rgb_image(
        image_source
    )

    try:
        inputs = processor(
            images=image,
            return_tensors="pt",
        ).to(device)

        with torch.inference_mode():
            output = model.get_image_features(
                pixel_values=inputs[
                    "pixel_values"
                ]
            )

        embedding = _extract_feature_tensor(
            output
        )

        return normalize_embedding(
            embedding
        )
    finally:
        image.close()


def generate_text_embedding(
    text: str,
) -> list[float]:
    """
    Generate a normalized CLIP text embedding in the same
    shared vector space as the image embeddings.
    """
    clean_text = " ".join(
        (text or "").strip().split()
    )

    if not clean_text:
        raise ValueError(
            "Text cannot be empty."
        )

    inputs = processor(
        text=[clean_text],
        return_tensors="pt",
        padding=True,
        truncation=True,
    ).to(device)

    with torch.inference_mode():
        output = model.get_text_features(
            input_ids=inputs["input_ids"],
            attention_mask=inputs[
                "attention_mask"
            ],
        )

    embedding = _extract_feature_tensor(
        output
    )

    return normalize_embedding(
        embedding
    )


# Backward compatibility with the existing Shopify sync service.
generate_embedding = generate_image_embedding
