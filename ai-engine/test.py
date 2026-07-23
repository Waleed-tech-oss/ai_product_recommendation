from services.clip_service import generate_text_embedding

embedding = generate_text_embedding("black nike shoes")

print(len(embedding))