import os
from pathlib import Path

import open_clip
import torch
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# CLIP weights (~350 MB) are cached here; on Cloudera AI this lives on project
# storage so application pods never re-download them.
CLIP_CACHE_DIR = os.getenv("CLIP_CACHE_DIR", str(Path.home() / ".cache" / "clip"))

_model = None
_preprocess = None
_tokenizer = None


def _get_clip():
    global _model, _preprocess, _tokenizer
    if _model is None:
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai", cache_dir=CLIP_CACHE_DIR
        )
        _tokenizer = open_clip.get_tokenizer("ViT-B-32")
        _model.eval()
    return _model, _preprocess, _tokenizer


def generate_embedding(image_path: str, text: str) -> list[float]:
    model, preprocess, tokenizer = _get_clip()

    img = Image.open(image_path).convert("RGB")
    img_tensor = preprocess(img).unsqueeze(0)
    text_tokens = tokenizer([text])

    with torch.no_grad():
        img_emb = model.encode_image(img_tensor)
        img_emb /= img_emb.norm(dim=-1, keepdim=True)
        txt_emb = model.encode_text(text_tokens)
        txt_emb /= txt_emb.norm(dim=-1, keepdim=True)
        combined = (img_emb + txt_emb) / 2
        combined /= combined.norm(dim=-1, keepdim=True)

    return combined.squeeze().tolist()


if __name__ == "__main__":
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    test_image = BASE_DIR / "data" / "images" / "catalog" / "0857777004195.jpg"
    embedding = generate_embedding(str(test_image), "RXBAR Blueberry Protein Bar")
    print(f"Dimensions: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")
