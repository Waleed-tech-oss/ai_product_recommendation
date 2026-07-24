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
            "name": product.get("name"),
            "description": product.get("description"),
            "category": product.get("category"),
            "subCategory": product.get("subCategory"),
            "articleType": product.get("articleType"),
            "gender": product.get("gender"),
            "color": product.get("color"),
            "season": product.get("season"),
            "usage": product.get("usage"),
            "image": product.get("image"),
            "price": product.get("price"),
            "score": float(score)
})

    similarities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return similarities[:top_k]