import numpy as np


def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    return np.dot(vec1, vec2) / (
        np.linalg.norm(vec1) * np.linalg.norm(vec2)
    )


def find_similar_products(query_embedding, products, top_k=5):

    similarities = []

    for product in products:

        embedding = product.get("embedding")

        if not embedding:
            continue

        score = cosine_similarity(query_embedding, embedding)

        similarities.append({
            "_id": str(product["_id"]),
            "name": product["name"],
            "image": product["image"],
            "category": product["category"],
            "price": product["price"],
            "score": float(score)
        })

    similarities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return similarities[:top_k]