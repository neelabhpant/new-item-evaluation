import os

import requests

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "product-catalog")


def _run_knn_query(embedding: list[float], k: int, category: str | None = None) -> list[dict]:
    knn_body: dict = {
        "vector": embedding,
        "k": k,
    }
    if category:
        knn_body["filter"] = {"term": {"category": category}}

    query = {
        "size": k,
        "query": {
            "knn": {
                "embedding": knn_body,
            }
        },
        "_source": [
            "sku", "name", "brand", "category", "price",
            "image_path", "claims", "ingredients",
        ],
    }

    resp = requests.post(
        f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_search",
        json=query,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()

    hits = resp.json()["hits"]["hits"]
    results = []
    for hit in hits:
        source = hit["_source"]
        results.append({
            "sku": source.get("sku", ""),
            "name": source.get("name", ""),
            "brand": source.get("brand", ""),
            "category": source.get("category", ""),
            "price": source.get("price", 0),
            "image_path": source.get("image_path", ""),
            "claims": source.get("claims", ""),
            "ingredients": source.get("ingredients", ""),
            "similarity_score": round(hit["_score"], 4),
        })

    return results


def search_similar_products(embedding: list[float], k: int = 10, category: str | None = None) -> list[dict]:
    """Legacy category-filtered search. Use search_all_products for cross-category analysis."""
    if category and category.lower() not in ("other", "other snacks", "auto-detect"):
        results = _run_knn_query(embedding, k, category)
        if results:
            return results

    return _run_knn_query(embedding, k)


def search_all_products(embedding: list[float], k: int = 20) -> list[dict]:
    """Unfiltered k-NN search across all products for cross-category analysis."""
    return _run_knn_query(embedding, k)


def group_by_category(products: list[dict]) -> list[dict]:
    """Group products by category, sorted by max similarity descending."""
    groups: dict[str, list[dict]] = {}
    for p in products:
        cat = p.get("category", "Unknown")
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(p)

    result = []
    for cat, prods in groups.items():
        prods.sort(key=lambda x: x["similarity_score"], reverse=True)
        result.append({
            "category": cat,
            "count": len(prods),
            "max_similarity": prods[0]["similarity_score"],
            "products": prods,
        })

    result.sort(key=lambda x: x["max_similarity"], reverse=True)
    return result


if __name__ == "__main__":
    from pathlib import Path
    from embedding_client import generate_embedding

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    test_image = BASE_DIR / "data" / "images" / "catalog" / "0857777004195.jpg"

    embedding = generate_embedding(str(test_image), "RXBAR Blueberry Protein Bar")
    results = search_similar_products(embedding, k=5)
    print(f"Found {len(results)} similar products:\n")
    for p in results:
        print(f"  {p['similarity_score']:.2%} | {p['name']} | {p['brand']} | {p['category']}")
