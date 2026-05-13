"""
Create the product-catalog OpenSearch index with the knn_vector mapping.

Idempotent: deletes the index first if it already exists. Safe to re-run.

Usage:
    python scripts/create_index.py
"""

import os
import sys
import requests

OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.environ.get("OPENSEARCH_INDEX", "product-catalog")

MAPPING = {
    "settings": {
        "index": {
            "knn": True
        }
    },
    "mappings": {
        "properties": {
            "sku": {"type": "keyword"},
            "name": {"type": "text"},
            "description": {"type": "text"},
            "category": {"type": "keyword"},
            "subcategory": {"type": "keyword"},
            "brand": {"type": "keyword"},
            "price": {"type": "float"},
            "image_path": {"type": "keyword"},
            "ingredients": {"type": "text"},
            "claims": {"type": "keyword"},
            "status": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 512,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "lucene",
                },
            },
        }
    },
}


def main():
    url = f"{OPENSEARCH_URL}/{INDEX_NAME}"

    head = requests.head(url, timeout=10)
    if head.status_code == 200:
        print(f"Index '{INDEX_NAME}' already exists. Deleting...")
        resp = requests.delete(url, timeout=30)
        if resp.status_code not in (200, 404):
            print(f"  FAILED to delete: {resp.status_code} {resp.text}")
            sys.exit(1)
        print("  Deleted.")

    print(f"Creating index '{INDEX_NAME}' with knn_vector mapping (dim=512, hnsw, cosinesimil)...")
    resp = requests.put(
        url,
        json=MAPPING,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        print(f"FAILED: {resp.status_code} {resp.text}")
        sys.exit(1)

    print(f"Created. Response: {resp.json()}")


if __name__ == "__main__":
    main()
