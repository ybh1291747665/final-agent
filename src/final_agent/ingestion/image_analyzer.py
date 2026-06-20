"""Image analyser — calls VLM API (Qwen-VL / GPT-4V) for image descriptions."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

from openai import OpenAI

from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

# Matches ![](path) or ![alt](path) in Markdown
_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def analyze_images_in_markdown(
    markdown_path: str | Path,
    images_root: str | Path,
    settings: Settings | None = None,
) -> str:
    """Scan a Markdown file for image references, call VLM for each, inject descriptions.

    Args:
        markdown_path: Path to the MinerU-generated Markdown file.
        images_root: Directory where MinerU extracted images (relative paths in md resolve here).
        settings: Application settings.

    Returns:
        The modified Markdown text with image descriptions appended.
    """
    markdown_path = Path(markdown_path).resolve()
    images_root = Path(images_root).resolve()

    if settings is None:
        settings = load_settings()

    v = settings.vision
    if not v.enabled:
        logger.info("Vision analysis disabled — skipping image descriptions")
        return markdown_path.read_text(encoding="utf-8")

    if not v.api_key or v.api_key.startswith("sk-your-"):
        logger.warning("Vision API key not configured — skipping image descriptions")
        return markdown_path.read_text(encoding="utf-8")

    text = markdown_path.read_text(encoding="utf-8")
    client = OpenAI(api_key=v.api_key, base_url=v.base_url)

    images = _IMG_RE.findall(text)
    if not images:
        logger.info("No images found in %s", markdown_path.name)
        return text

    logger.info("Found %d image(s) in %s — analysing with %s/%s",
                len(images), markdown_path.name, v.provider, v.model)

    count = 0
    for img_rel in images:
        if count >= v.max_images_per_doc:
            break
        img_path = images_root / img_rel
        if not img_path.exists():
            logger.warning("Image file not found: %s", img_path)
            continue

        try:
            desc = _describe_image(client, img_path, v.model, v.prompt)
            if desc:
                block = f'\n\n> 📷 **图片分析**: {desc}\n'
                text = text.replace(f"]({img_rel})", f"]({img_rel}){block}")
                count += 1
                logger.info("  [%d/%d] %s → %d chars", count, len(images), img_rel, len(desc))
        except Exception as e:
            logger.error("VLM failed for %s: %s", img_rel, e)

    logger.info("Image analysis complete: %d/%d images described", count, len(images))
    return text


def _describe_image(
    client: OpenAI,
    image_path: Path,
    model: str,
    prompt: str,
) -> str:
    """Send an image to the VLM and return its description."""
    ext = image_path.suffix.lower()
    mime = _mime_for_ext(ext)
    if not mime:
        raise ValueError(f"Unsupported image format: {ext}")

    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content or ""


def _mime_for_ext(ext: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, "")
