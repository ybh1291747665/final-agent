"""Streamlit UI — upload, ingest, ask, review, configure APIs, knowledge base, hallucination guard."""

from __future__ import annotations

import logging
import shutil
import uuid as _uuid
from datetime import datetime as _dt
from pathlib import Path

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

import os as _os
PROJECT_ROOT = Path(_os.environ.get("FINAL_AGENT_ROOT", str(Path(__file__).resolve().parents[3])))
DATA_DIR = PROJECT_ROOT / "data"
ENV_PATH = PROJECT_ROOT / ".env"
CONV_PATH = DATA_DIR / "conversations.json"

from final_agent.ingestion import import_document
from final_agent.knowledge import build, create_course, delete_empty_course, list_course_index_info, list_documents, metadata_total, chroma_delete_doc, bm25_delete_doc, remove_document, chroma_get_chunks, chroma_migrate_legacy_course, list_courses, rebuild_course_knowledge
from final_agent.retrieval import search as retrieval_search
from final_agent.retrieval.pipeline import deep_search
from final_agent.runtime_monitoring import get_runtime_monitor
from final_agent.generation import answer_question, verify_answer
from final_agent.generation.answer_generator import answer_deep
from final_agent.generation.summarizer import summarize_document
from final_agent.settings import load_settings, Settings
from final_agent.schemas import ReadingContext
from final_agent.ui.agent_client import AgentApiClient, AgentApiError
from final_agent.ui.charts import cjk_font_properties, unpack_pie_result
from final_agent.ui.conversation_compression import compress_conversations
from final_agent.ui.knowledge_status import format_knowledge_status
from final_agent.ui.study_coach_view import format_agent_timeline, format_critic_warnings, format_evidence_snapshots, format_quality_report, format_study_coach_summary, format_trace_lines
from final_agent.ui.theme import app_header_html, apple_theme_css
from final_agent.ui.pdf_viewer import pdf_documents, render_pdf_viewer
from final_agent.ui.workspace import (
    build_chunk_registry,
    course_maintenance_copy,
    course_management_guidance,
    citation_pdf_target,
    evidence_status_summary,
    evidence_popover_config,
    effective_course_filter,
    format_citation_label,
    format_course_maintenance_failure,
    format_course_migration_summary,
    format_course_repair_summary,
    format_build_result_message,
    input_placeholder,
    latest_assistant_evidence,
    mode_display_names,
    mode_group_options,
    replace_citation_labels,
    reading_context_caption,
    reading_context_payload,
    validation_status_summary,
    validation_summary,
    workspace_column_weights,
)

logger = logging.getLogger(__name__)

# ============================== .env helpers ==============================

def _read_env(key: str) -> str:
    if not ENV_PATH.exists():
        return ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith(f"{key}="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _write_env(key: str, value: str) -> None:
    lines = (ENV_PATH.read_text(encoding="utf-8").splitlines()
             if ENV_PATH.exists() else [])
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _refresh_settings() -> Settings:
    from dotenv import load_dotenv as _ld
    # Force-reload .env into os.environ
    _ld(ENV_PATH, override=True)
    import final_agent.settings as _mod
    _mod._CONFIG_CACHE = None
    return _mod.load_settings()


# ============================== Persistence ==============================

def _save_conversations(state: AppState) -> None:
    """Persist conversations to disk as JSON."""
    import json as _json
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state.conversations = compress_conversations(state.conversations)
    payload = {
        "conversations": state.conversations,
        "active_conv_id": state.active_conv_id,
        "course_id": state.course_id,
        "query_mode": state.query_mode,
        "model_prefs": state.model_prefs,
    }
    CONV_PATH.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_conversations() -> tuple[dict, str, str, str, dict]:
    """Return (conversations_dict, active_conv_id, course_id, query_mode, model_prefs) from disk."""
    import json as _json
    if not CONV_PATH.exists():
        return {}, "", "", "qa", _default_model_prefs()
    try:
        data = _json.loads(CONV_PATH.read_text(encoding="utf-8"))
        return (
            data.get("conversations", {}),
            data.get("active_conv_id", ""),
            data.get("course_id", ""),
            data.get("query_mode", "qa"),
            data.get("model_prefs", _default_model_prefs()),
        )
    except Exception:
        return {}, "", "", "qa", _default_model_prefs()


# ============================== AppState ==============================

def _new_conv_id() -> str:
    return _uuid.uuid4().hex[:8]


def _new_conv_name() -> str:
    return f"新对话 {_dt.now().strftime('%H:%M')}"


def _default_model_prefs() -> dict[str, str]:
    return {
        "qa": "deepseek-v4-flash",
        "deep": "deepseek-v4-flash",
        "page_by_page": "deepseek-v4-flash",
        "full_summary": "deepseek-v4-flash",
        "key_points": "deepseek-v4-flash",
    }


class AppState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    conversations: dict[str, dict] = Field(default_factory=dict)  # {conv_id: {name, history[]}}
    active_conv_id: str = ""
    current_doc: str = ""
    build_counter: int = 0
    course_id: str = ""         # "" = all courses
    query_mode: str = "qa"      # qa | deep | page_by_page | full_summary | key_points | study_coach
    model_prefs: dict[str, str] = Field(default_factory=_default_model_prefs)
    agent_session_id: str = ""
    active_pdf_doc: str = ""
    active_pdf_page: int = 1
    pdf_zoom: int = 100
    pdf_viewer_open: bool = False
    page_boost_enabled: bool = True

    def _current_history(self) -> list[dict]:
        """Return chat history of the active conversation."""
        conv = self.conversations.get(self.active_conv_id)
        if conv is None:
            return []
        return conv.get("history", [])

    def _add_message(self, role: str, **kwargs) -> None:
        """Append a message to the active conversation's history."""
        if not self.active_conv_id:
            return
        conv = self.conversations.setdefault(self.active_conv_id, {"name": _new_conv_name(), "history": []})
        msg = {"role": role, **kwargs}
        conv["history"].append(msg)

    def _ensure_default(self) -> None:
        """Create a default conversation if none exist."""
        if not self.conversations:
            cid = _new_conv_id()
            self.conversations[cid] = {"name": "默认对话", "history": []}
            self.active_conv_id = cid


def init_state() -> Settings:
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()
        # Restore persisted conversations
        convs, active, course, mode, prefs = _load_conversations()
        if convs:
            st.session_state.app_state.conversations = convs
            if active and active in convs:
                st.session_state.app_state.active_conv_id = active
            elif convs:
                st.session_state.app_state.active_conv_id = next(iter(convs.keys()))
        st.session_state.app_state.course_id = course
        st.session_state.app_state.query_mode = mode or "qa"
        if prefs:
            # Merge with defaults so new modes always have a value
            merged = _default_model_prefs()
            merged.update(prefs)
            st.session_state.app_state.model_prefs = merged
    st.session_state.app_state._ensure_default()
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    return st.session_state.settings

# ================================= UI =================================

st.set_page_config(page_title="final-agent", layout="wide", initial_sidebar_state="expanded")
st.markdown(apple_theme_css(), unsafe_allow_html=True)

settings = init_state()
app_state: AppState = st.session_state.app_state
question = st.session_state.pop("pending_question", "")

if app_state.pdf_viewer_open:
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] {
  display: none !important;
}
[data-testid="stMain"],
[data-testid="stAppViewContainer"] > section {
  margin-left: 0 !important;
}
div[data-testid="stBottom"] {
  left: 0 !important;
  width: 100vw !important;
}
</style>
""".strip(),
        unsafe_allow_html=True,
    )

st.markdown(
    app_header_html(
        knowledge_status=format_knowledge_status(list_course_index_info(settings=st.session_state.settings), app_state.course_id),
        active_mode=mode_display_names().get(app_state.query_mode, app_state.query_mode),
        course_label=app_state.course_id or "全部课件",
    ),
    unsafe_allow_html=True,
)

# ====================== SIDEBAR ======================

with st.sidebar:
    # --- LLM API ---
    st.markdown('<div class="fa-section-label">模型与 API</div>', unsafe_allow_html=True)
    with st.expander("DeepSeek 问答模型", expanded=not _read_env("DEEPSEEK_API_KEY")):
        dk = _read_env("DEEPSEEK_API_KEY")
        du = _read_env("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
        ak = st.text_input(
            "API Key", value=dk if dk and not dk.startswith("sk-your-") else "",
            type="password", placeholder="sk-...", key="deepseek_key"
        )
        au = st.text_input("Base URL", value=du, key="deepseek_url")
        if st.button("保存", key="save_deepseek"):
            if ak.strip():
                _write_env("DEEPSEEK_API_KEY", ak.strip())
                _write_env("DEEPSEEK_BASE_URL", au.strip())
                st.session_state.settings = _refresh_settings()
                app_state.build_counter += 1
                st.success("已保存")
                st.rerun()
            else:
                st.error("请输入 Key")
        if not dk or dk.startswith("sk-your-"):
            st.info("需配置 DeepSeek Key")

    # --- Vision API ---
    vision_on = st.checkbox(
        "启用图片分析 (Doubao)",
        key="vision_toggle",
        help="导入 PDF 时自动用 VLM 分析图片内容"
    )
    if vision_on:
        vk = _read_env("ARK_API_KEY")
        vu = _read_env("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
        v_key = st.text_input("火山方舟 Key", value=vk, type="password", key="vision_key_inp")
        v_url = st.text_input("VLM Base URL", value=vu, key="vision_url_inp")
        v_model = st.selectbox("模型", ["doubao-seed-2-0-pro-260215", "doubao-seed-2-0-lite-260428"], key="vision_model_sel")
        if st.button("保存 Vision"):
            if v_key.strip():
                _write_env("ARK_API_KEY", v_key.strip())
                _write_env("ARK_BASE_URL", v_url.strip())
                st.session_state.settings = _refresh_settings()
                st.success("已保存")
                st.rerun()
            else:
                st.error("请输入 Key")

    st.divider()

    # --- Conversations ---
    st.markdown('<div class="fa-section-label">学习会话</div>', unsafe_allow_html=True)

    convs = app_state.conversations
    # Sort: newest first (by conv_id order in dict — insertion order)
    for cid in list(convs.keys()):
        c = convs[cid]
        n_msgs = len(c.get("history", []))
        label = f"{'当前 · ' if cid == app_state.active_conv_id else ''}{c['name']} ({n_msgs})"
        col_a, col_b = st.columns([4, 1])
        with col_a:
            if st.button(label, key=f"conv_{cid}", use_container_width=True):
                app_state.active_conv_id = cid
                _save_conversations(app_state)
                st.rerun()
        with col_b:
            if len(convs) > 1:
                if st.button("删除", key=f"delconv_{cid}", help="删除此对话"):
                    del convs[cid]
                    if app_state.active_conv_id == cid:
                        app_state.active_conv_id = next(iter(convs.keys()), "")
                    _save_conversations(app_state)
                    st.rerun()

    if st.button("新建对话", use_container_width=True):
        cid = _new_conv_id()
        convs[cid] = {"name": _new_conv_name(), "history": []}
        app_state.active_conv_id = cid
        _save_conversations(app_state)
        st.rerun()

    st.divider()

    # --- Hallucination stats ---
    with st.expander("幻觉统计", expanded=True):
        all_flags: list[dict] = []
        for msg in app_state._current_history():
            if msg.get("role") == "assistant" and msg.get("flags"):
                all_flags.extend(msg["flags"])
        if not all_flags:
            st.caption("当前对话暂无校验数据")
        else:
            import matplotlib.pyplot as plt
            clean = sum(1 for f in all_flags if not f.get("flagged"))
            suspect = sum(1 for f in all_flags if f.get("flagged"))
            total = len(all_flags)
            fig, ax = plt.subplots(figsize=(3, 3))
            colors = ["#2ecc71", "#e74c3c"]
            labels = [f"通过 ({clean})", f"疑似 ({suspect})"]
            sizes = [clean, suspect]
            if suspect == 0:
                sizes = [clean]
                labels = labels[:1]
                colors = colors[:1]
            cjk_font = cjk_font_properties()
            wedges, texts, autotexts = unpack_pie_result(ax.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct="%1.1f%%" if suspect > 0 else None,
                startangle=90,
                pctdistance=0.6,
                textprops={"fontproperties": cjk_font} if cjk_font else None,
            ))
            for t in [*texts, *autotexts]:
                if cjk_font:
                    t.set_fontproperties(cjk_font)
                t.set_fontsize(9)
                t.set_fontweight("bold")
            ax.set_title(f"累计校验 {total} 处引用", fontsize=10, fontproperties=cjk_font)
            st.pyplot(fig)
            plt.close(fig)
            suspect_rate = suspect / total * 100 if total else 0
            if suspect_rate == 0:
                st.success(f"全部通过：{total} 处引用均与原文一致")
            elif suspect_rate < 20:
                st.info(f"疑似率 {suspect_rate:.1f}% — 整体可信，少数需核实")

    st.divider()

    with st.expander("Runtime metrics", expanded=False):
        metrics = get_runtime_monitor().snapshot()
        retrieval_metrics = metrics["retrieval"]
        model_metrics = metrics["model_calls"]
        st.caption(
            f"Retrieval: {retrieval_metrics['count']} calls, "
            f"avg {retrieval_metrics['avg_latency_ms']:.1f} ms, "
            f"course hit {retrieval_metrics['course_hit_rate']:.0%}"
        )
        st.caption(
            f"Model: {model_metrics['count']} calls, "
            f"avg {model_metrics['avg_latency_ms']:.1f} ms, "
            f"tokens {model_metrics['prompt_tokens']} + {model_metrics['completion_tokens']}"
        )
        st.caption(f"Estimated model cost: ${model_metrics['estimated_cost_usd']:.4f}")

    st.divider()

    # --- Course & Mode ---
    st.markdown('<div class="fa-section-label">检索范围</div>', unsafe_allow_html=True)
    courses = list_courses(settings=st.session_state.settings)
    course_options = ["全部课件"] + courses
    current_course_label = "全部课件" if not app_state.course_id else app_state.course_id
    if current_course_label not in course_options:
        current_course_label = course_options[0]
    selected_course = st.selectbox(
        "课程",
        course_options,
        index=course_options.index(current_course_label),
        key="course_sel",
    )
    new_course = "" if selected_course == "全部课件" else selected_course
    if new_course != app_state.course_id:
        app_state.course_id = new_course
        _save_conversations(app_state)
    course_guidance = course_management_guidance(app_state.course_id)
    st.caption(course_guidance["upload_assignment"])
    if not app_state.course_id:
        st.warning(course_guidance["all_courses_warning"])

    with st.expander("新建课程", expanded=False):
        new_course_name = st.text_input(
            "课程名称",
            key="new_course_name",
            placeholder="例如：软件工程",
        )
        if st.button("创建课程", key="create_course", use_container_width=True):
            course_name = new_course_name.strip()
            if not course_name:
                st.warning("请输入课程名称")
            else:
                try:
                    created = create_course(course_name, settings=st.session_state.settings)
                    app_state.course_id = course_name
                    _save_conversations(app_state)
                    if created:
                        st.success(f"已创建课程：{course_name}")
                    else:
                        st.info(f"课程已存在，已切换到：{course_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建课程失败: {e}")
        if app_state.course_id:
            st.divider()
            st.caption("只有没有文档的课程可以删除。")
            if st.button("删除当前空课程", key="delete_empty_course", use_container_width=True):
                deleted = delete_empty_course(app_state.course_id, settings=st.session_state.settings)
                if deleted:
                    removed_course = app_state.course_id
                    app_state.course_id = ""
                    _save_conversations(app_state)
                    st.success(f"已删除空课程：{removed_course}")
                    st.rerun()
                else:
                    st.warning("当前课程已有文档，不能作为空课程删除")

    grouped_modes = [
        (key, f"{group} · {label}")
        for group, options in mode_group_options().items()
        for key, label in options
    ]
    mode_keys = [key for key, _label in grouped_modes]
    mode_options = [label for _key, label in grouped_modes]
    current_mode_idx = mode_keys.index(app_state.query_mode) if app_state.query_mode in mode_keys else 0
    selected_mode = st.selectbox(
        "模式",
        mode_options,
        index=current_mode_idx,
        key="mode_sel",
    )
    new_mode = mode_keys[mode_options.index(selected_mode)]
    if new_mode != app_state.query_mode:
        app_state.query_mode = new_mode
        _save_conversations(app_state)

    # Model picker for current mode
    model_names = ["deepseek-v4-flash", "deepseek-v4-pro"]
    current_model = app_state.model_prefs.get(new_mode, "deepseek-v4-flash")
    if current_model not in model_names:
        current_model = "deepseek-v4-flash"
    selected_model = st.radio(
        "模型选择",
        model_names,
        index=model_names.index(current_model),
        key="model_radio",
        horizontal=True,
    )
    if selected_model != app_state.model_prefs.get(new_mode):
        app_state.model_prefs[new_mode] = selected_model
        _save_conversations(app_state)

    # Document picker for summary modes
    if app_state.query_mode in ("page_by_page", "full_summary", "key_points"):
        docs_meta = list_documents(settings=st.session_state.settings)
        if app_state.course_id:
            docs_meta = {k: v for k, v in docs_meta.items() if v.get("course_id", "") == app_state.course_id}
        doc_ids = list(docs_meta.keys())
        if doc_ids:
            current_doc_idx = doc_ids.index(app_state.current_doc) if app_state.current_doc in doc_ids else len(doc_ids) - 1
            app_state.current_doc = st.selectbox(
                "目标文档",
                doc_ids,
                index=current_doc_idx,
                key="doc_sel",
            )
        else:
            st.caption("当前课程无文档")

    st.divider()

    # --- Knowledge Base ---
    st.markdown('<div class="fa-section-label">知识库</div>', unsafe_allow_html=True)

    docs = list_documents(settings=st.session_state.settings)
    if docs:
        total = metadata_total(settings=st.session_state.settings)
        st.caption(f"已导入 {len(docs)} 篇文档，共 {total} 个 chunk")
        for d_id, info in docs.items():
            c_count = info.get("chunk_count", 0)
            label = f"{d_id} ({c_count} chunks)"
            with st.expander(label):
                st.caption(f"来源: {info.get('source_path', '?')}")
                st.caption(f"导入: {info.get('imported_at', '?')[:19]}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("查看", key=f"view_{d_id}", use_container_width=True):
                        st.session_state[f"show_chunks_{d_id}"] = not st.session_state.get(f"show_chunks_{d_id}", False)
                with col2:
                    if st.button("删除", key=f"del_{d_id}", use_container_width=True):
                        cur_s = st.session_state.settings
                        n1 = chroma_delete_doc(d_id, settings=cur_s)
                        n2 = bm25_delete_doc(d_id, settings=cur_s)
                        remove_document(d_id, settings=cur_s)
                        app_state.build_counter += 1
                        st.success(f"已删除: {n1} Chroma + BM25 chunks")
                        st.rerun()

                if st.session_state.get(f"show_chunks_{d_id}"):
                    try:
                        chunks = chroma_get_chunks(d_id, settings=st.session_state.settings)
                        st.caption(f"共 {len(chunks)} 个 chunk:")
                        for ch in chunks:
                            hdr = " > ".join(ch.heading_path) if ch.heading_path else "(top)"
                            st.text(f"[{ch.chunk_id[:8]}] {hdr}\n{ch.text[:120]}...")
                    except Exception:
                        st.caption("(无法加载 chunk)")
    else:
        st.caption("知识库为空，上传课件开始")

    maintenance_copy = course_maintenance_copy()
    with st.expander(maintenance_copy["expander_label"], expanded=False):
        target_course = app_state.course_id or "默认课程"
        st.caption(maintenance_copy["caption_template"].format(course_id=target_course))
        if st.button(maintenance_copy["repair_button"], use_container_width=True):
            try:
                summary = rebuild_course_knowledge(target_course, settings=st.session_state.settings)
                st.success(format_course_repair_summary(summary))
                app_state.build_counter += 1
            except Exception as e:
                st.error(format_course_maintenance_failure("repair", e))
        if st.button(maintenance_copy["advanced_button"], use_container_width=True):
            try:
                summary = chroma_migrate_legacy_course(target_course, settings=st.session_state.settings)
                st.success(format_course_migration_summary(summary))
            except Exception as e:
                st.error(format_course_maintenance_failure("migration", e))

    uploader_key = f"uploader_{app_state.build_counter}"
    uploaded = st.file_uploader("上传 PDF 或 Markdown", type=["pdf", "md"], key=uploader_key)
    if uploaded:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        upload_dir = DATA_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = upload_dir / uploaded.name
        tmp_path.write_bytes(uploaded.read())
        cur = st.session_state.settings

        # Quick page-count peek for PDFs
        if uploaded.name.lower().endswith(".pdf"):
            try:
                import pypdfium2 as _pdfium
                _pdf = _pdfium.PdfDocument(str(tmp_path))
                _total = len(_pdf)
                _max = min(cur.vision.max_pages, _total)
                _batches = (_max + cur.vision.pages_per_batch - 1) // cur.vision.pages_per_batch
                _conc = min(cur.vision.concurrent_batches, _batches)
                st.info(f"PDF 共 {_total} 页（处理前 {_max} 页），{_batches} 批 × {_conc} 路并行 → Doubao API")
                _pdf.close()
            except Exception:
                pass

        with st.spinner(f"导入: {uploaded.name} ..."):
            try:
                chunks = import_document(str(tmp_path), settings=cur, course_id=app_state.course_id or "")
                summary = build(chunks, source_path=str(tmp_path), settings=cur)
                app_state.build_counter += 1
                st.success(format_build_result_message(summary))
                st.rerun()
            except Exception as e:
                st.error(f"失败: {e}")
                with st.expander("详情"):
                    import traceback
                    st.code(traceback.format_exc())

    if st.button("清空知识库", use_container_width=True):
        shutil.rmtree(str(DATA_DIR / "vector_db"), ignore_errors=True)
        app_state.build_counter += 1
        st.success("已清除")
        st.rerun()

    st.divider()
    st.caption("Doubao API + BGE + Chroma + DeepSeek")
    st.caption("防幻觉: L2 语义校验 (threshold=0.3)")

# ============================== Helpers ==============================

def _build_registry(results):
    """Build chunk_registry dict from ScoredChunk list."""
    docs = list_documents(settings=st.session_state.settings)
    return build_chunk_registry(results, docs)


def _run_hallucination_check(ans, results, cur):
    """Run hallucination guard and return flag_data list."""
    chunk_map = {r.chunk.chunk_id: r.chunk for r in results}
    try:
        verified = verify_answer(ans, chunk_map, settings=cur)
    except Exception:
        return []
    if not verified or not verified.flags:
        return []
    return [{
        "sentence": f.sentence,
        "cited_chunk_id": f.cited_chunk_id,
        "similarity_score": f.similarity_score,
        "flagged": f.flagged,
    } for f in verified.flags]


def _show_hallucination(flag_data, chunk_registry=None):
    """Display hallucination check results."""
    if not flag_data:
        return
    chunk_registry = chunk_registry or {}
    clean_n = sum(1 for f in flag_data if not f["flagged"])
    bad_n = len(flag_data) - clean_n
    if bad_n > 0:
        st.error(f"幻觉检测: {bad_n}/{len(flag_data)} 处疑似编造")
    else:
        st.success(f"防幻觉通过 ({clean_n}/{len(flag_data)})")
    with st.expander(f"逐句校验 ({len(flag_data)} 处)"):
        for f in flag_data:
            sim = f["similarity_score"]
            cid = f["cited_chunk_id"]
            label = format_citation_label(cid, chunk_registry.get(cid, {}))
            if f["flagged"]:
                st.error(f"[{label}] sim={sim:.3f}  {f['sentence'][:120]}")
            else:
                st.success(f"[{label}] sim={sim:.3f}  {f['sentence'][:120]}")


def _show_citations(ans, chunk_registry):
    """Display citation sources."""
    if not ans or not ans.citations:
        return
    with st.expander(f"引用来源 ({len(ans.citations)} 个 chunk)"):
        for cid in ans.citations:
            if cid in chunk_registry:
                ci = chunk_registry[cid]
                label = format_citation_label(cid, ci)
                st.caption(f"**[{label}]** {ci['heading']} (score={ci['score']:.3f}, {ci['source']})")
                _show_pdf_link(ci, f"answer-citation-{cid}")
                st.text(ci["text"][:400])
            else:
                st.caption(f"**[{format_citation_label(cid, {})}]** (未命中)")


def _show_study_coach_evidence(snapshots, key_prefix="coach-evidence"):
    with st.expander("Study Coach evidence", expanded=False):
        for index, (snapshot, line) in enumerate(
            zip(snapshots or [], format_evidence_snapshots(snapshots or []))
        ):
            st.markdown(f"- {line}")
            _show_pdf_link(snapshot, f"{key_prefix}-{index}")


def _course_filter() -> list[str] | None:
    return effective_course_filter(
        app_state.course_id,
        list_course_index_info(settings=st.session_state.settings),
    )


def _reading_context_dict() -> dict | None:
    return reading_context_payload(
        app_state.active_pdf_doc,
        app_state.active_pdf_page,
        app_state.page_boost_enabled,
        viewer_open=app_state.pdf_viewer_open,
    )


def _reading_context_model() -> ReadingContext | None:
    payload = _reading_context_dict()
    return ReadingContext.model_validate(payload) if payload else None


def _show_pdf_link(entry: dict, key: str) -> None:
    target = citation_pdf_target(entry)
    if target is None:
        return
    if st.button("在 PDF 中查看", key=key, use_container_width=False):
        app_state.active_pdf_doc, app_state.active_pdf_page = target
        app_state.pdf_viewer_open = True
        st.rerun()


def _run_study_coach_turn(prompt: str, cids: list[str] | None) -> None:
    client = AgentApiClient()
    try:
        if not app_state.agent_session_id:
            response = client.create_session(
                prompt,
                cids or [],
                reading_context=_reading_context_dict(),
            )
            app_state.agent_session_id = response["session_id"]
        else:
            response = client.send_message(
                app_state.agent_session_id,
                prompt,
                reading_context=_reading_context_dict(),
            )

        mastery_response = client.get_mastery(app_state.agent_session_id)
        trace_response = client.get_trace(app_state.agent_session_id)
        content = format_study_coach_summary(response, mastery_response.get("mastery", {}))
        st.markdown(content)
        _show_study_coach_evidence(response.get("evidence_snapshots", []), "live-coach")
        with st.expander("Answer quality", expanded=False):
            for line in format_quality_report(response.get("quality_report")):
                st.markdown(f"- {line}")
        with st.expander("Study Coach tool trace", expanded=False):
            for line in format_trace_lines(trace_response.get("trace", [])):
                st.markdown(f"- {line}")
        with st.expander("Multi-Agent timeline", expanded=False):
            for line in format_agent_timeline(response.get("agent_trace", [])):
                st.markdown(f"- {line}")
        with st.expander("Critic warnings", expanded=False):
            for line in format_critic_warnings(response.get("critic_warnings", [])):
                st.markdown(f"- {line}")
        app_state._add_message("assistant", content=content, evidence_snapshots=response.get("evidence_snapshots", []))
    except AgentApiError as e:
        st.error(f"Study Coach API error: {e}")


def _render_history() -> None:
    for message_index, msg in enumerate(app_state._current_history()):
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])
            reg = msg.get("chunk_registry", {})

            if role == "assistant" and msg.get("flags"):
                _show_hallucination(msg["flags"], reg)

            if role == "assistant" and msg.get("citations"):
                with st.expander(f"引用来源 ({len(msg['citations'])} 个 chunk)"):
                    for cid in msg["citations"]:
                        if cid in reg:
                            ci = reg[cid]
                            label = format_citation_label(cid, ci)
                            st.caption(
                                f"**[{label}]** {ci['heading']} "
                                f"(score={ci['score']:.3f}, {ci['source']})"
                            )
                            _show_pdf_link(ci, f"history-{message_index}-{cid}")
                            st.text(ci["text"][:400])
                        else:
                            st.caption(f"**[{format_citation_label(cid, {})}]** (未在检索结果中)")


            if role == "assistant" and msg.get("evidence_snapshots"):
                _show_study_coach_evidence(
                    msg.get("evidence_snapshots", []),
                    f"history-coach-{message_index}",
                )


def _render_evidence_tab(evidence: dict) -> None:
    citations = evidence.get("citations", [])
    registry = evidence.get("chunk_registry", {})
    st.caption(evidence_status_summary(evidence))
    if not citations:
        st.caption("生成回答后，这里会显示引用 chunk、来源和分数。")
        return
    st.caption(f"最近回答引用了 {len(citations)} 个 chunk")
    for cid in citations:
        if cid in registry:
            ci = registry[cid]
            label = format_citation_label(cid, ci)
            with st.expander(f"{label} · {ci['source']} · score={ci['score']:.3f}"):
                st.caption(ci["heading"])
                st.text(ci["text"][:700])
        else:
            st.caption(f"**[{format_citation_label(cid, {})}]** (未在检索结果中)")


def _render_validation_tab(evidence: dict) -> None:
    flags = evidence.get("flags", [])
    registry = evidence.get("chunk_registry", {})
    summary = validation_summary(flags)
    st.caption(validation_status_summary(flags))
    if summary["total"] == 0:
        st.caption("最近回答暂无逐句引用校验数据。")
        return
    if summary["suspect"]:
        st.error(f"疑似 {summary['suspect']}/{summary['total']} 处")
    else:
        st.success(f"通过 {summary['clean']}/{summary['total']} 处")
    with st.expander("逐句校验详情", expanded=True):
        for flag in flags:
            sim = flag.get("similarity_score", 0)
            cid = str(flag.get("cited_chunk_id", ""))
            label = format_citation_label(cid, registry.get(cid, {}))
            sentence = str(flag.get("sentence", ""))[:160]
            if flag.get("flagged"):
                st.error(f"[{label}] sim={sim:.3f}  {sentence}")
            else:
                st.success(f"[{label}] sim={sim:.3f}  {sentence}")


def _render_coach_tab() -> None:
    st.caption("Study Coach 使用现有 FastAPI session contract。")
    prompt = st.text_area(
        "学习目标 / 回答",
        key="coach_tab_prompt",
        height=120,
        placeholder="例如：帮我复习软件配置管理，先出一道题",
    )
    if st.button("运行 Study Coach", key="coach_tab_run", use_container_width=True):
        if prompt.strip():
            app_state._add_message("user", content=prompt.strip())
            _run_study_coach_turn(prompt.strip(), _course_filter())
            _save_conversations(app_state)
        else:
            st.warning("请输入学习目标或回答")


# ====================== MAIN: Workspace ======================

viewer_documents = list_documents(settings=st.session_state.settings)
available_pdf_documents = pdf_documents(viewer_documents)
if not app_state.active_pdf_doc and available_pdf_documents:
    app_state.active_pdf_doc = list(available_pdf_documents)[-1]
reading_toggle_col, context_col = st.columns([0.22, 0.78], gap="medium")
with reading_toggle_col:
    pdf_toggle_label = "收起 PDF" if app_state.pdf_viewer_open else "打开 PDF"
    if st.button(
        pdf_toggle_label,
        key="pdf_viewer_open_button",
        disabled=not available_pdf_documents,
        use_container_width=True,
    ):
        app_state.pdf_viewer_open = not app_state.pdf_viewer_open
        st.rerun()
if app_state.pdf_viewer_open:
    st.markdown(
        """
<style>
section[data-testid="stSidebar"] {
  display: none !important;
}
[data-testid="stMain"],
[data-testid="stAppViewContainer"] > section {
  margin-left: 0 !important;
}
div[data-testid="stBottom"] {
  left: 0 !important;
  width: 100vw !important;
}
</style>
""".strip(),
        unsafe_allow_html=True,
    )
with context_col:
    st.caption(reading_context_caption(_reading_context_dict(), viewer_documents))

if app_state.pdf_viewer_open:
    app_state.page_boost_enabled = st.toggle(
        "当前页加权",
        value=app_state.page_boost_enabled,
        key="page_boost_enabled",
    )

workspace_weights = workspace_column_weights(app_state.pdf_viewer_open)
if len(workspace_weights) == 2:
    question_workspace, pdf_workspace = st.columns(list(workspace_weights), gap="large")
else:
    question_workspace = st.container()
    pdf_workspace = None

question_workspace.__enter__()

title_col, evidence_col = st.columns([0.60, 0.40], gap="medium")
with title_col:
    st.subheader("Ask / Summarize")
    st.caption(
        f"当前模式：{mode_display_names().get(app_state.query_mode, app_state.query_mode)} · "
        f"课程范围：{app_state.course_id or '全部课件'}"
    )

with evidence_col:
    popover = evidence_popover_config()
    st.caption(popover["caption"])
    with st.popover(popover["label"], use_container_width=True):
        st.subheader("Evidence")
        evidence = latest_assistant_evidence(app_state._current_history())
        evidence_tab, validation_tab, coach_tab = st.tabs(["Evidence", "Validation", "Coach"])
        with evidence_tab:
            _render_evidence_tab(evidence)
        with validation_tab:
            _render_validation_tab(evidence)
        with coach_tab:
            _render_coach_tab()

_render_history()

# --- Pending input submitted by the page-level chat box ---
if question:
    cur = st.session_state.settings
    if not cur.models_llm.api_key or cur.models_llm.api_key.startswith("sk-your-"):
        st.error("请先在侧边栏配置 DeepSeek API Key")
    else:
        app_state._add_message("user", content=question)
        mode = app_state.query_mode

        # Auto-name conversation from first question
        conv = app_state.conversations.get(app_state.active_conv_id)
        if conv and conv["name"].startswith("新对话 "):
            conv["name"] = question[:30] + ("..." if len(question) > 30 else "")
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            cids = _course_filter()

            # ==================== QA mode ====================
            if mode == "qa":
                with st.spinner("检索中..."):
                    try:
                        results = retrieval_search(
                            question,
                            settings=cur,
                            top_k=10,
                            course_ids=cids,
                            reading_context=_reading_context_model(),
                        )
                    except Exception as e:
                        st.error(f"检索失败: {e}")
                        results = []

                if not results:
                    st.warning("未找到相关内容，请先上传课件")
                else:
                    with st.spinner("生成答案..."):
                        try:
                            ans = answer_question(question, results, settings=cur, model=app_state.model_prefs.get("qa"))
                        except Exception as e:
                            st.error(f"生成失败: {e}")
                            import traceback
                            with st.expander("详情"):
                                st.code(traceback.format_exc())
                            ans = None

                    if ans and ans.answer:
                        chunk_registry = _build_registry(results)
                        display_answer = replace_citation_labels(ans.answer, chunk_registry)
                        st.markdown(display_answer)
                        flag_data = _run_hallucination_check(ans, results, cur)
                        _show_hallucination(flag_data, chunk_registry)
                        _show_citations(ans, chunk_registry)

                        app_state._add_message("assistant", content=display_answer,
                            flags=flag_data, citations=ans.citations, chunk_registry=chunk_registry)

            # ==================== Deep QA mode ====================
            elif mode == "deep":
                with st.spinner("深度检索中（高召回+上下文扩展）..."):
                    try:
                        results = deep_search(
                            question,
                            settings=cur,
                            course_ids=cids,
                            reading_context=_reading_context_model(),
                        )
                    except Exception as e:
                        st.error(f"检索失败: {e}")
                        results = []

                if not results:
                    st.warning("未找到相关内容，请先上传课件")
                else:
                    st.info(f"已检索到 {len(results)} 个相关 chunk（含邻居扩展）")
                    with st.spinner("综合生成答案（多文档对比）..."):
                        try:
                            ans = answer_deep(question, results, settings=cur, model=app_state.model_prefs.get("deep"))
                        except Exception as e:
                            st.error(f"生成失败: {e}")
                            import traceback
                            with st.expander("详情"):
                                st.code(traceback.format_exc())
                            ans = None

                    if ans and ans.answer:
                        chunk_registry = _build_registry(results)
                        display_answer = replace_citation_labels(ans.answer, chunk_registry)
                        st.markdown(display_answer)
                        _show_citations(ans, chunk_registry)
                        app_state._add_message("assistant", content=display_answer,
                            citations=ans.citations, chunk_registry=chunk_registry)

            # ==================== Study Coach mode ====================
            elif mode == "study_coach":
                _run_study_coach_turn(question, cids)

            # ==================== Summary modes ====================
            elif mode in ("page_by_page", "full_summary", "key_points"):
                doc_id = app_state.current_doc
                if not doc_id:
                    docs_meta = list_documents(settings=cur)
                    if app_state.course_id:
                        docs_meta = {k: v for k, v in docs_meta.items() if v.get("course_id", "") == app_state.course_id}
                    if docs_meta:
                        doc_id = list(docs_meta.keys())[-1]
                    else:
                        st.warning("请先上传课件")
                        doc_id = ""

                if doc_id:
                    mode_labels = {"page_by_page": "逐页输出", "full_summary": "全文总结", "key_points": "重点总结"}
                    with st.spinner(f"生成{mode_labels.get(mode, mode)}中..."):
                        try:
                            summary = summarize_document(doc_id, mode, settings=cur, model=app_state.model_prefs.get(mode))
                        except Exception as e:
                            st.error(f"总结失败: {e}")
                            import traceback
                            with st.expander("详情"):
                                st.code(traceback.format_exc())
                            summary = f"总结失败: {e}"

                    st.markdown(summary)
                    app_state._add_message("assistant", content=summary)

# Autosave conversations after every interaction
_save_conversations(app_state)
question_workspace.__exit__(None, None, None)

if pdf_workspace is not None:
    with pdf_workspace:
        render_pdf_viewer(
            app_state,
            list_documents(settings=st.session_state.settings),
        )

submitted_question = st.chat_input(input_placeholder(app_state.query_mode))
if submitted_question:
    st.session_state.pending_question = submitted_question
    st.rerun()
