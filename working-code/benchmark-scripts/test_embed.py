"""Smoke test: embed a single in-memory image with Gemini Embedding 2 at 3072 dims.

If this prints `Vector length: 3072` the embedding pipeline is wired correctly:
- google-genai SDK installed and importable
- GEMINI_API_KEY forwarded into the container and visible to genai.Client()
- target model accepts image input
- output_dimensionality=3072 is honored
"""

import io
import os
import sys

from PIL import Image
from google import genai
from google.genai import types

MODEL_ID = "gemini-embedding-2"
TARGET_DIMS = 3072


def main() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set in container env. Check docker_forward_env in profile config.")

    img = Image.new("RGB", (256, 256), color=(80, 130, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    client = genai.Client()

    result = client.models.embed_content(
        model=MODEL_ID,
        contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/png")],
        config=types.EmbedContentConfig(output_dimensionality=TARGET_DIMS),
    )

    vec = result.embeddings[0].values
    print(f"Vector length: {len(vec)}")


if __name__ == "__main__":
    main()
