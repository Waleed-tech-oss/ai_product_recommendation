import os
import uuid
import requests

UPLOAD_DIR = "uploads/shopify"

os.makedirs(UPLOAD_DIR, exist_ok=True)


def download_image(image_url: str):

    extension = image_url.split(".")[-1].split("?")[0]

    filename = f"{uuid.uuid4()}.{extension}"

    filepath = os.path.join(
        UPLOAD_DIR,
        filename
    )

    response = requests.get(image_url, timeout=30)
    response.raise_for_status()

    with open(filepath, "wb") as file:
        file.write(response.content)

    return filepath