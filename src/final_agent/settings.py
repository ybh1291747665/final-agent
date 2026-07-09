"""Application settings, loaded from config.yaml and overridable via env vars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class LLMSettings(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.1
    max_tokens: int = 4096


class EmbeddingSettings(BaseModel):
    model_name: str = "BAAI/bge-large-zh-v1.5"
    device: str = "cpu"


class RerankerSettings(BaseModel):
    model_name: str = "BAAI/bge-reranker-v2-m3"
    device: str = "cpu"


class ChunkingSettings(BaseModel):
    size: int = 512
    overlap: int = 64
    separators: list[str] = ["## ", "### ", "#### "]


class RetrievalSettings(BaseModel):
    top_k: int = 10
    similarity_threshold: float = 0.5
    min_matches: int = 3
    bm25_weight: float = 0.3
    dense_weight: float = 0.7
    review_top_k: int = 30
    review_similarity_threshold: float = 0.3
    neighbor_expand: int = 2


class VectorStoreSettings(BaseModel):
    type: str = "chroma"
    persist_dir: str = "data/vector_db"
    collection_name: str = "final_agent_knowledge"


class DataSettings(BaseModel):
    upload_dir: str = "data/uploads"
    markdown_dir: str = "data/markdown"
    chunks_dir: str = "data/chunks"
    images_dir: str = "data/images"


class VisionSettings(BaseModel):
    enabled: bool = False
    provider: str = "volcengine"
    model: str = "doubao-seed-2-0-pro-260215"
    api_key: str = ""
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    max_images_per_doc: int = 50
    prompt: str = "请详细描述这张图片的内容。如果图片包含文字、公式、图表或数据，请逐一提取并说明。"
    # PDF→Markdown (Doubao API)
    page_dpi: int = 150
    max_pages: int = 100
    pages_per_batch: int = 3
    concurrent_batches: int = 5


class SummarySettings(BaseModel):
    max_chunks_per_batch: int = 20
    temperature: float = 0.3


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------

class Settings(BaseModel):
    """Aggregated application settings."""

    models_llm: LLMSettings = Field(default_factory=LLMSettings)
    models_embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    models_reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    summary: SummarySettings = Field(default_factory=SummarySettings)

    # Project root (derived)
    project_root: Path = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_CONFIG_CACHE: Optional[Settings] = None


def _env_var(value: str, project_root: Path | None = None) -> str:
    """Resolve ${VAR:-default} placeholders, first from os.environ, then from .env file."""
    import re

    def _read_dotenv(var: str) -> str | None:
        """Try to read a key directly from the project's .env file."""
        if project_root is None:
            return None
        env_path = project_root / ".env"
        if not env_path.exists():
            return None
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(f"{var}="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")
        return None

    def replacer(match):
        var = match.group(1)
        default = match.group(2) if match.lastindex >= 2 else ""
        # os.environ first, then .env file direct read, then default
        return os.environ.get(var) or _read_dotenv(var) or default

    return re.sub(r"\$\{(\w+)(?::-(.*?))?\}", replacer, value)


def _fixup_ascii(value: str) -> str:
    """Replace full-width confusable characters with ASCII equivalents."""
    table = str.maketrans({
        '\uff1a': ':',   # full-width colon ：
        '\uff0d': '-',   # full-width hyphen －
        '\uff0f': '/',   # full-width slash ／
        '\uff0e': '.',   # full-width period ．  
        '\uff20': '@',   # full-width at sign ＠
        '\uff1d': '=',   # full-width equals ＝
        '\uff06': '&',   # full-width ampersand ＆
        '\uff1f': '?',   # full-width question mark ？
        '\uff03': '#',   # full-width hash ＃
    })
    value = value.translate(table)
    return value.encode('ascii', errors='ignore').decode('ascii')


def _sanitize_llm(raw: dict) -> LLMSettings:
    """Build LLMSettings, coercing None→'' and fixing full-width chars."""
    raw = dict(raw)
    if raw.get("api_key") is None:
        raw["api_key"] = ""
    if raw.get("base_url") is None:
        raw["base_url"] = "https://api.deepseek.com/v1"
    raw["api_key"] = _fixup_ascii(raw["api_key"])
    raw["base_url"] = _fixup_ascii(raw["base_url"])
    return LLMSettings(**raw)


def _sanitize_vlm(raw: dict) -> VisionSettings:
    """Build VisionSettings, coercing None→'' and fixing full-width chars."""
    raw = dict(raw)
    if raw.get("api_key") is None:
        raw["api_key"] = ""
    if raw.get("base_url") is None:
        raw["base_url"] = "https://ark.cn-beijing.volces.com/api/v3"
    raw["api_key"] = _fixup_ascii(raw["api_key"])
    raw["base_url"] = _fixup_ascii(raw["base_url"])
    return VisionSettings(**raw)


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """Load settings from YAML config file, resolving env-var placeholders."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    # Resolve project root — prefer env var (set by main.py ui command)
    root = os.environ.get("FINAL_AGENT_ROOT", "")
    project_root = Path(root) if root else Path(__file__).resolve().parent.parent.parent

    if config_path is None:
        config_path = project_root / "config.yaml"

    if not config_path.exists():
        _CONFIG_CACHE = Settings()
        return _CONFIG_CACHE

    raw_text = config_path.read_text(encoding="utf-8")
    resolved_text = _env_var(raw_text, project_root=project_root)
    raw = yaml.safe_load(resolved_text) or {}

    _CONFIG_CACHE = Settings(
        models_llm=_sanitize_llm(raw.get("models", {}).get("llm", {})),
        models_embedding=EmbeddingSettings(**raw.get("models", {}).get("embedding", {})),
        models_reranker=RerankerSettings(**raw.get("models", {}).get("reranker", {})),
        chunking=ChunkingSettings(**raw.get("chunking", {})),
        retrieval=RetrievalSettings(**raw.get("retrieval", {})),
        vector_store=VectorStoreSettings(**raw.get("vector_store", {})),
        data=DataSettings(**raw.get("data", {})),
        vision=_sanitize_vlm(raw.get("vision", {})),
        summary=SummarySettings(**raw.get("summary", {})),
        project_root=project_root,
    )
    # Resolve all relative data paths against project root
    _resolve_paths(_CONFIG_CACHE)
    return _CONFIG_CACHE


def _resolve_paths(s: Settings) -> None:
    """Convert relative directory paths in settings to absolute (based on project_root)."""
    root = s.project_root
    for field_name, attr in [
        ("upload_dir", s.data), ("markdown_dir", s.data),
        ("chunks_dir", s.data), ("images_dir", s.data),
    ]:
        val = getattr(attr, field_name)
        p = Path(val)
        if not p.is_absolute():
            setattr(attr, field_name, str(root / p))
    # Vector store persist_dir
    vp = Path(s.vector_store.persist_dir)
    if not vp.is_absolute():
        s.vector_store.persist_dir = str(root / vp)
