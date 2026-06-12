"""PDF parser — invokes MinerU via CLI subprocess, producing Markdown output."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def parse_pdf(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    settings: Settings | None = None,
    *,
    backend: str = "pipeline",
    effort: str = "medium",
    lang: str = "ch",
    start_page: int | None = None,
    end_page: int | None = None,
) -> Path:
    """Convert a PDF to Markdown using MinerU CLI.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to write output. Defaults to ``settings.data.markdown_dir``.
        settings: Application settings (auto-loaded if omitted).
        backend: MinerU backend (hybrid-engine, pipeline, etc.).
        effort: ``medium`` or ``high`` (hybrid only).
        lang: OCR language hint.
        start_page: Optional start page (0-based).
        end_page: Optional end page (0-based, inclusive).

    Returns:
        Path to the generated Markdown file.

    Raises:
        FileNotFoundError: If ``pdf_path`` does not exist.
        subprocess.CalledProcessError: If MinerU exits with non-zero.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if settings is None:
        settings = load_settings()

    if output_dir is None:
        output_dir = settings.data.markdown_dir
    output_dir = Path(output_dir)
    # Ensure absolute — fall back to project_root if still relative
    if not output_dir.is_absolute():
        output_dir = settings.project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mineru",
        "-p", str(pdf_path),
        "-o", str(output_dir),
        "-b", backend,
        "-l", lang,
    ]

    if backend.startswith("hybrid"):
        cmd += ["--effort", effort]

    if start_page is not None:
        cmd += ["-s", str(start_page)]
    if end_page is not None:
        cmd += ["-e", str(end_page)]

    # Use ModelScope instead of HuggingFace — avoids Windows symlink permission issues
    models_dir = str(settings.project_root / "data" / "models")
    env = dict(os.environ)
    env["MINERU_MODEL_SOURCE"] = "modelscope"
    env["MODELSCOPE_CACHE"] = models_dir
    env.setdefault("HF_HUB_CACHE", models_dir)
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    logger.info("Running MinerU (modelscope): %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)

    if result.returncode != 0:
        stderr_tail = result.stderr.strip().split("\n")[-10:]
        logger.error("MinerU stderr (last 10 lines):\n%s", "\n".join(stderr_tail))
        # Check for known issues
        if "WinError 1314" in result.stderr or "WinError 5" in result.stderr:
            raise RuntimeError(
                "MinerU 无法下载模型：Windows 权限不足。请以**管理员身份**运行终端，"
                "或在 Windows 设置中开启「开发者模式」（设置 → 隐私和安全性 → 开发者选项 → 开发者模式）。"
            )
        if "CUDA is not available" in result.stderr:
            raise RuntimeError(
                "MinerU hybrid-engine 需要 CUDA GPU，但你当前没有。已在代码中改为 pipeline 后端，"
                "请确认 pdf_parser.py 的 backend 参数为 'pipeline'。"
            )
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

    logger.info("MinerU stdout:\n%s", result.stdout)

    # MinerU writes <output_dir>/<pdf_stem>/<pdf_stem>.md
    markdown_file = output_dir / pdf_path.stem / f"{pdf_path.stem}.md"
    if not markdown_file.exists():
        # Some versions use a flat layout
        fallback = output_dir / f"{pdf_path.stem}.md"
        if fallback.exists():
            return fallback
        raise FileNotFoundError(f"MinerU output not found at {markdown_file} or {fallback}")

    return markdown_file
