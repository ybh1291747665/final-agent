"""Doubao PDF parser — renders PDF pages as PNG, sends to Doubao VLM API for Markdown extraction.

Replaces MinerU with a pure-API approach.  Pages are rendered at configurable DPI,
grouped into small batches (default 3) so the model preserves cross-page context.
All batches are sent in parallel via ThreadPoolExecutor for speed.
"""

from __future__ import annotations

import base64
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pypdfium2 as pdfium
from openai import OpenAI

from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)

_MARKDOWN_PROMPT = """请将以下 PDF 页面内容转换为结构化的 Markdown 格式。

要求：
1. 使用 # / ## / ### 等标题层级保留文档结构
2. 表格使用 Markdown 表格格式（| ... |）
3. 数学公式使用 LaTeX 格式（$...$ 行内，$$...$$ 块级）
4. 列表、编号、引用等保持原格式
5. 不要遗漏任何文字内容
6. 用 [图片描述] 简要概括无法提取文字的图片内容
7. 只输出 Markdown，不要添加额外说明"""


def _render_page(page: pdfium.PdfPage, dpi: float) -> str:
    """Render a single PDF page to a base64-encoded PNG data URL."""
    bitmap = page.render(scale=dpi / 72.0)
    pil_img = bitmap.to_pil().convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _call_batch(
    batch_idx: int,
    start_page: int,
    end_page: int,
    page_data_urls: list[str],
    client: OpenAI,
    model: str,
) -> tuple[int, int, str]:
    """Call Doubao API for one batch. Returns (batch_idx, start_page, markdown)."""
    content: list[dict] = [{"type": "text", "text": _MARKDOWN_PROMPT}]
    for url in page_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    logger.info(
        "Batch %d: sending pages %d–%d to %s ...",
        batch_idx + 1, start_page + 1, end_page, model,
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=4096,
            temperature=0.1,
        )
        md = response.choices[0].message.content or ""
        logger.info(
            "Batch %d complete: pages %d–%d → %d chars",
            batch_idx + 1, start_page + 1, end_page, len(md),
        )
        return (batch_idx, start_page, md)
    except Exception as e:
        logger.error("Batch %d (pages %d–%d) failed: %s", batch_idx + 1, start_page + 1, end_page, e)
        return (batch_idx, start_page, f"\n\n> ⚠️ 第 {start_page + 1}–{end_page} 页解析失败: {e}\n\n")


def parse_pdf_doubao(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    settings: Settings | None = None,
) -> Path:
    """Convert a PDF to Markdown using Doubao VLM API.

    Renders every page as PNG upfront, then sends all batches to the Doubao
    vision model in parallel via ThreadPoolExecutor, and concatenates the
    returned Markdown in page order.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to write output. Defaults to ``settings.data.markdown_dir``.
        settings: Application settings (auto-loaded if omitted).

    Returns:
        Path to the generated Markdown file.

    Raises:
        FileNotFoundError: If ``pdf_path`` does not exist.
        RuntimeError: If the vision API key is not configured.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if settings is None:
        settings = load_settings()

    v = settings.vision
    if not v.api_key or v.api_key.startswith("sk-your-"):
        raise RuntimeError(
            "Doubao API key not configured. "
            "请在侧边栏配置火山方舟 ARK_API_KEY，或手动写入 .env 文件。"
        )

    if output_dir is None:
        output_dir = settings.data.markdown_dir
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = settings.project_root / output_dir

    # Match MinerU layout: <output_dir>/<pdf_stem>/<pdf_stem>.md
    doc_dir = output_dir / pdf_path.stem
    doc_dir.mkdir(parents=True, exist_ok=True)
    md_path = doc_dir / f"{pdf_path.stem}.md"

    # --- Phase 1: Render all pages upfront ---
    t0 = time.perf_counter()
    logger.info("Opening PDF with pypdfium2: %s", pdf_path.name)
    pdf = pdfium.PdfDocument(str(pdf_path))
    total_pages = len(pdf)
    max_pages = min(v.max_pages, total_pages)
    if total_pages > v.max_pages:
        logger.warning(
            "PDF has %d pages, limiting to max_pages=%d", total_pages, v.max_pages
        )

    dpi = v.page_dpi
    batch_size = max(1, v.pages_per_batch)
    total_batches = (max_pages + batch_size - 1) // batch_size

    logger.info("Rendering %d pages @ %d DPI …", max_pages, dpi)
    all_data_urls: list[str] = []
    for page_idx in range(max_pages):
        url = _render_page(pdf[page_idx], dpi)
        all_data_urls.append(url)
        if (page_idx + 1) % 10 == 0 or page_idx == max_pages - 1:
            logger.debug("  rendered %d/%d pages", page_idx + 1, max_pages)

    pdf.close()
    t1 = time.perf_counter()
    logger.info(
        "All %d pages rendered in %.1fs → %d batch(es) of ≤%d pages, %d concurrent",
        max_pages, t1 - t0, total_batches, batch_size, v.concurrent_batches,
    )

    # --- Phase 2: Parallel API calls ---
    client = OpenAI(api_key=v.api_key, base_url=v.base_url)
    max_workers = min(v.concurrent_batches, total_batches)

    # Build batch tasks: each is (batch_idx, start_page, end_page, [data_urls])
    tasks: list[tuple[int, int, int, list[str]]] = []
    for batch_idx in range(total_batches):
        start_page = batch_idx * batch_size
        end_page = min(start_page + batch_size, max_pages)
        tasks.append((batch_idx, start_page, end_page, all_data_urls[start_page:end_page]))

    results: dict[int, tuple[int, str]] = {}  # batch_idx → (start_page, markdown)
    logger.info("Dispatching %d batches (%d parallel) …", total_batches, max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_call_batch, bidx, sp, ep, urls, client, v.model): bidx
            for bidx, sp, ep, urls in tasks
        }
        for future in as_completed(futures):
            bidx, sp, md = future.result()
            results[bidx] = (sp, md)
            done = len(results)
            logger.info("Progress: %d/%d batches done", done, total_batches)

    # --- Phase 3: Concatenate in page order with page markers ---
    t2 = time.perf_counter()
    markdown_parts: list[str] = []
    for i in range(total_batches):
        sp, md = results[i]
        # Insert page marker: 1-based page number of the first page in this batch
        markdown_parts.append(f"<!-- page_start: {sp + 1} -->\n{md}")
    full_md = "\n\n".join(markdown_parts)
    md_path.write_text(full_md, encoding="utf-8")
    logger.info(
        "Doubao parsing complete: %d pages → %s (%d chars) | render %.1fs + api %.1fs = total %.1fs",
        max_pages, md_path.name, len(full_md),
        t1 - t0, t2 - t1, t2 - t0,
    )
    return md_path
