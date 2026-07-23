import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image

device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Using Device: {device}")

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

model.to(device)
model.eval()

print("✅ CLIP Loaded Successfully")


def normalize_embedding(embedding):
    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze().cpu().numpy().tolist()


def generate_image_embedding(image_path):

    image = Image.open(image_path).convert("RGB")

    inputs = processor(
        images=image,
        return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        outputs = model.get_image_features(**inputs)

    embedding = outputs.pooler_output

    return normalize_embedding(embedding)
#Backward compatibility
generate_embedding = generate_image_embedding


def generate_text_embedding(text):
    inputs = processor(
        text=[text],
        return_tensors="pt",
        padding=True,
        truncation=True
    ).to(device)

    with torch.no_grad():
        outputs = model.text_model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"]
        )
        embedding = model.text_projection(outputs.pooler_output)

    print(type(embedding))
    print(embedding.shape)

    return normalize_embedding(embedding)