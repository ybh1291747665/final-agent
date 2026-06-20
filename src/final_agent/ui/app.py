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
from final_agent.knowledge import build, bm25_load, list_documents, metadata_total, chroma_delete_doc, bm25_delete_doc, remove_document, chroma_get_chunks, chroma_get_all, list_courses
from final_agent.retrieval import search as retrieval_search
from final_agent.retrieval.pipeline import deep_search
from final_agent.generation import answer_question, verify_answer
from final_agent.generation.answer_generator import answer_deep
from final_agent.generation.summarizer import summarize_document
from final_agent.settings import load_settings, Settings
from final_agent.ui.agent_client import AgentApiClient, AgentApiError

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


@st.cache_resource
def ensure_knowledge_loaded(_h: str = "") -> bool:
    """Restore BM25 index from persisted JSON using all chunks in ChromaDB."""
    try:
        cur = load_settings()
        all_chunks = chroma_get_all(settings=cur)
        bm25_load(all_chunks, settings=cur)
    except Exception:
        pass
    return True


# ================================= UI =================================

st.set_page_config(page_title="final-agent", page_icon="📚", layout="wide")
st.title("📚 final-agent — 期末复习助手")

settings = init_state()
app_state: AppState = st.session_state.app_state

with st.spinner("加载知识库..."):
    ensure_knowledge_loaded(str(app_state.build_counter))
st.empty()

# ====================== SIDEBAR ======================

with st.sidebar:
    # --- LLM API ---
    st.header("🔑 API 配置")
    with st.expander("🤖 DeepSeek (问答)", expanded=not _read_env("DEEPSEEK_API_KEY")):
        dk = _read_env("DEEPSEEK_API_KEY")
        du = _read_env("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
        ak = st.text_input(
            "API Key", value=dk if dk and not dk.startswith("sk-your-") else "",
            type="password", placeholder="sk-...", key="deepseek_key"
        )
        au = st.text_input("Base URL", value=du, key="deepseek_url")
        if st.button("💾 保存", key="save_deepseek"):
            if ak.strip():
                _write_env("DEEPSEEK_API_KEY", ak.strip())
                _write_env("DEEPSEEK_BASE_URL", au.strip())
                st.session_state.settings = _refresh_settings()
                app_state.build_counter += 1
                st.success("✅ 已保存")
                st.rerun()
            else:
                st.error("请输入 Key")
        if not dk or dk.startswith("sk-your-"):
            st.info("💡 需配置 DeepSeek Key")

    # --- Vision API ---
    vision_on = st.checkbox(
        "🖼️ 启用图片分析 (Doubao)",
        key="vision_toggle",
        help="导入 PDF 时自动用 VLM 分析图片内容"
    )
    if vision_on:
        vk = _read_env("ARK_API_KEY")
        vu = _read_env("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
        v_key = st.text_input("火山方舟 Key", value=vk, type="password", key="vision_key_inp")
        v_url = st.text_input("VLM Base URL", value=vu, key="vision_url_inp")
        v_model = st.selectbox("模型", ["doubao-seed-2-0-pro-260215", "doubao-seed-2-0-lite-260428"], key="vision_model_sel")
        if st.button("💾 保存 Vision"):
            if v_key.strip():
                _write_env("ARK_API_KEY", v_key.strip())
                _write_env("ARK_BASE_URL", v_url.strip())
                st.session_state.settings = _refresh_settings()
                st.success("✅ 已保存")
                st.rerun()
            else:
                st.error("请输入 Key")

    st.divider()

    # --- Conversations ---
    st.header("💬 对话")

    convs = app_state.conversations
    # Sort: newest first (by conv_id order in dict — insertion order)
    for cid in list(convs.keys()):
        c = convs[cid]
        n_msgs = len(c.get("history", []))
        label = f"{'🔵 ' if cid == app_state.active_conv_id else '⚪ '}{c['name']} ({n_msgs})"
        col_a, col_b = st.columns([4, 1])
        with col_a:
            if st.button(label, key=f"conv_{cid}", use_container_width=True):
                app_state.active_conv_id = cid
                _save_conversations(app_state)
                st.rerun()
        with col_b:
            if len(convs) > 1:
                if st.button("🗑️", key=f"delconv_{cid}", help="删除此对话"):
                    del convs[cid]
                    if app_state.active_conv_id == cid:
                        app_state.active_conv_id = next(iter(convs.keys()), "")
                    _save_conversations(app_state)
                    st.rerun()

    if st.button("➕ 新建对话", use_container_width=True):
        cid = _new_conv_id()
        convs[cid] = {"name": _new_conv_name(), "history": []}
        app_state.active_conv_id = cid
        _save_conversations(app_state)
        st.rerun()

    st.divider()

    # --- Hallucination stats ---
    with st.expander("📊 幻觉统计", expanded=True):
        all_flags: list[dict] = []
        for msg in app_state._current_history():
            if msg.get("role") == "assistant" and msg.get("flags"):
                all_flags.extend(msg["flags"])
        if not all_flags:
            st.caption("📭 当前对话暂无校验数据")
        else:
            import matplotlib.pyplot as plt
            clean = sum(1 for f in all_flags if not f.get("flagged"))
            suspect = sum(1 for f in all_flags if f.get("flagged"))
            total = len(all_flags)
            fig, ax = plt.subplots(figsize=(3, 3))
            colors = ["#2ecc71", "#e74c3c"]
            labels = [f"✅ 通过 ({clean})", f"⚠️ 疑似 ({suspect})"]
            sizes = [clean, suspect]
            if suspect == 0:
                sizes = [clean]
                labels = labels[:1]
                colors = colors[:1]
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct="%1.1f%%" if suspect > 0 else None,
                startangle=90,
                pctdistance=0.6,
            )
            for t in autotexts:
                t.set_fontsize(9)
                t.set_fontweight("bold")
            ax.set_title(f"累计校验 {total} 处引用", fontsize=10)
            st.pyplot(fig)
            plt.close(fig)
            suspect_rate = suspect / total * 100 if total else 0
            if suspect_rate == 0:
                st.success(f"🎉 全部通过！{total} 处引用均与原文一致")
            elif suspect_rate < 20:
                st.info(f"疑似率 {suspect_rate:.1f}% — 整体可信，少数需核实")

    st.divider()

    # --- Course & Mode ---
    st.header("🔍 检索设置")
    courses = list_courses(settings=st.session_state.settings)
    course_options = ["全部课件"] + courses
    current_course_label = "全部课件" if not app_state.course_id else app_state.course_id
    if current_course_label not in course_options:
        current_course_label = course_options[0]
    selected_course = st.selectbox(
        "📚 课程",
        course_options,
        index=course_options.index(current_course_label),
        key="course_sel",
    )
    new_course = "" if selected_course == "全部课件" else selected_course
    if new_course != app_state.course_id:
        app_state.course_id = new_course
        _save_conversations(app_state)

    mode_options = ["🔍 问答", "📖 深度问答", "📄 逐页输出", "📋 全文总结", "⭐ 重点总结", "🎓 Study Coach"]
    mode_keys = ["qa", "deep", "page_by_page", "full_summary", "key_points", "study_coach"]
    current_mode_idx = mode_keys.index(app_state.query_mode) if app_state.query_mode in mode_keys else 0
    selected_mode = st.selectbox(
        "模  式",
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
        "⚡ 模型选择",
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
                "📎 目标文档",
                doc_ids,
                index=current_doc_idx,
                key="doc_sel",
            )
        else:
            st.caption("⚠️ 当前课程无文档")

    st.divider()

    # --- Knowledge Base ---
    st.header("📄 知识库")

    docs = list_documents(settings=st.session_state.settings)
    if docs:
        total = metadata_total(settings=st.session_state.settings)
        st.caption(f"已导入 {len(docs)} 篇文档，共 {total} 个 chunk")
        for d_id, info in docs.items():
            c_count = info.get("chunk_count", 0)
            label = f"📎 {d_id} ({c_count} chunks)"
            with st.expander(label):
                st.caption(f"来源: {info.get('source_path', '?')}")
                st.caption(f"导入: {info.get('imported_at', '?')[:19]}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 查看", key=f"view_{d_id}", use_container_width=True):
                        st.session_state[f"show_chunks_{d_id}"] = not st.session_state.get(f"show_chunks_{d_id}", False)
                with col2:
                    if st.button("🗑️ 删除", key=f"del_{d_id}", use_container_width=True):
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
        st.caption("📭 知识库为空，上传课件开始")

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
                st.info(f"📝 PDF 共 {_total} 页（处理前 {_max} 页），{_batches} 批 × {_conc} 路并行 → Doubao API")
                _pdf.close()
            except Exception:
                pass

        with st.spinner(f"导入: {uploaded.name} ..."):
            try:
                chunks = import_document(str(tmp_path), settings=cur, course_id=app_state.course_id or "")
                summary = build(chunks, source_path=str(tmp_path), settings=cur)
                app_state.build_counter += 1
                st.success(f"✅ {summary['chunks']} chunks")
                st.rerun()
            except Exception as e:
                st.error(f"失败: {e}")
                with st.expander("详情"):
                    import traceback
                    st.code(traceback.format_exc())

    if st.button("🗑️ 清空知识库", use_container_width=True):
        shutil.rmtree(str(DATA_DIR / "vector_db"), ignore_errors=True)
        app_state.build_counter += 1
        st.success("已清除")
        st.rerun()

    st.divider()
    st.caption("Doubao API + BGE + Chroma + DeepSeek")
    st.caption("防幻觉: L2 语义校验 (threshold=0.3)")

# ====================== MAIN: Chat ======================

st.subheader("💬 问答")

for msg in app_state._current_history():
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])

        if role == "assistant" and msg.get("flags"):
            clean_n = sum(1 for f in msg["flags"] if not f.get("flagged"))
            bad_n = sum(1 for f in msg["flags"] if f.get("flagged"))
            total_n = len(msg["flags"])
            if bad_n > 0:
                st.error(f"⚠️ 幻觉检测: {bad_n}/{total_n} 处疑似编造")
            else:
                st.success(f"✅ 防幻觉校验通过 ({clean_n}/{total_n} 处于原文一致)")

            with st.expander(f"🔍 逐句校验详情 ({total_n} 处引用)"):
                for f in msg["flags"]:
                    sim = f["similarity_score"]
                    cid = f["cited_chunk_id"][:8]
                    if f["flagged"]:
                        st.error(f"⚠️ [{cid}] 相似度={sim:.3f}   {f['sentence'][:120]}")
                    else:
                        st.success(f"✅ [{cid}] 相似度={sim:.3f}   {f['sentence'][:120]}")

        if role == "assistant" and msg.get("citations"):
            with st.expander(f"📖 引用来源 ({len(msg['citations'])} 个 chunk)"):
                for cid in msg["citations"]:
                    reg = msg.get("chunk_registry", {})
                    if cid in reg:
                        ci = reg[cid]
                        st.caption(
                            f"**[{cid[:8]}]** {ci['heading']} "
                            f"(score={ci['score']:.3f}, {ci['source']})"
                        )
                        st.text(ci["text"][:400])
                    else:
                        st.caption(f"**[{cid[:8]}]** (未在检索结果中)")

# ============================== Helpers ==============================

def _build_registry(results):
    """Build chunk_registry dict from ScoredChunk list."""
    reg = {}
    for r in results:
        c = r.chunk
        h = " > ".join(c.heading_path) if c.heading_path else "(top)"
        reg[c.chunk_id] = {"heading": h, "text": c.text, "score": r.score, "source": r.source}
    return reg


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


def _show_hallucination(flag_data):
    """Display hallucination check results."""
    if not flag_data:
        return
    clean_n = sum(1 for f in flag_data if not f["flagged"])
    bad_n = len(flag_data) - clean_n
    if bad_n > 0:
        st.error(f"⚠️ 幻觉检测: {bad_n}/{len(flag_data)} 处疑似编造")
    else:
        st.success(f"✅ 防幻觉通过 ({clean_n}/{len(flag_data)})")
    with st.expander(f"🔍 逐句校验 ({len(flag_data)} 处)"):
        for f in flag_data:
            sim = f["similarity_score"]
            cid = f["cited_chunk_id"][:8]
            if f["flagged"]:
                st.error(f"⚠️ [{cid}] sim={sim:.3f}  {f['sentence'][:120]}")
            else:
                st.success(f"✅ [{cid}] sim={sim:.3f}  {f['sentence'][:120]}")


def _show_citations(ans, chunk_registry):
    """Display citation sources."""
    if not ans or not ans.citations:
        return
    with st.expander(f"📖 引用来源 ({len(ans.citations)} 个 chunk)"):
        for cid in ans.citations:
            if cid in chunk_registry:
                ci = chunk_registry[cid]
                st.caption(f"**[{cid[:8]}]** {ci['heading']} (score={ci['score']:.3f}, {ci['source']})")
                st.text(ci["text"][:400])
            else:
                st.caption(f"**[{cid[:8]}]** (未命中)")

# --- Input ---
question = st.chat_input(
    "输入你的问题..." if app_state.query_mode in ("qa", "deep")
    else f"输入指令（当前模式：{app_state.query_mode}）..."
)
if question:
    cur = st.session_state.settings
    if not cur.models_llm.api_key or cur.models_llm.api_key.startswith("sk-your-"):
        st.error("⚠️ 请先在侧边栏配置 DeepSeek API Key")
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
            # --- Build course filter ---
            cids: list[str] | None = None
            if app_state.course_id:
                cids = [app_state.course_id]

            # ==================== QA mode ====================
            if mode == "qa":
                with st.spinner("检索中..."):
                    try:
                        results = retrieval_search(question, settings=cur, top_k=10, course_ids=cids)
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
                        st.markdown(ans.answer)
                        chunk_registry = _build_registry(results)
                        flag_data = _run_hallucination_check(ans, results, cur)
                        _show_hallucination(flag_data)
                        _show_citations(ans, chunk_registry)

                        app_state._add_message("assistant", content=ans.answer,
                            flags=flag_data, citations=ans.citations, chunk_registry=chunk_registry)

            # ==================== Deep QA mode ====================
            elif mode == "deep":
                with st.spinner("深度检索中（高召回+上下文扩展）..."):
                    try:
                        results = deep_search(question, settings=cur, course_ids=cids)
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
                        st.markdown(ans.answer)
                        chunk_registry = _build_registry(results)
                        _show_citations(ans, chunk_registry)
                        app_state._add_message("assistant", content=ans.answer,
                            citations=ans.citations, chunk_registry=chunk_registry)

            # ==================== Study Coach mode ====================
            elif mode == "study_coach":
                client = AgentApiClient()
                try:
                    if not app_state.agent_session_id:
                        response = client.create_session(question, cids or [])
                        app_state.agent_session_id = response["session_id"]
                    else:
                        response = client.send_message(app_state.agent_session_id, question)

                    plan_lines = [
                        f"- [{ 'x' if step.get('completed') else ' ' }] {step.get('objective', '')} (`{step.get('tool_name', '')}`)"
                        for step in response.get("plan", [])
                    ]
                    quiz = response.get("quiz") or {}
                    grade = response.get("grade") or {}
                    content = "\n".join([
                        f"**Status:** `{response.get('status')}`",
                        "",
                        "**Plan:**",
                        *plan_lines,
                        "",
                        f"**Question:** {quiz.get('prompt', '(none)')}",
                        f"**Grade:** {grade.get('score', 'waiting')}",
                        grade.get("feedback", ""),
                    ])
                    st.markdown(content)
                    app_state._add_message("assistant", content=content)
                except AgentApiError as e:
                    st.error(f"Study Coach API error: {e}")

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
