from __future__ import annotations

import html


def apple_theme_css() -> str:
    """Return the Streamlit CSS used by the Apple-like study workspace."""
    return """
<style>
:root {
  --fa-bg: #f5f5f7;
  --fa-surface: #ffffff;
  --fa-surface-soft: #fbfbfd;
  --fa-text: #1d1d1f;
  --fa-muted: #6e6e73;
  --fa-border: rgba(0, 0, 0, 0.08);
  --fa-blue: #007aff;
  --fa-blue-soft: rgba(0, 122, 255, 0.12);
  --fa-green: #34c759;
  --fa-red: #ff3b30;
  --fa-radius: 18px;
  --fa-control-radius: 12px;
  --fa-shadow: 0 18px 45px rgba(0, 0, 0, 0.07);
  --fa-font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
}

html,
body,
[data-testid="stApp"],
[class*="css"] {
  font-family: var(--fa-font);
  color: var(--fa-text);
  letter-spacing: 0;
}

[data-testid="stApp"],
.stApp {
  color: var(--fa-text);
  background:
    radial-gradient(circle at top left, rgba(0, 122, 255, 0.09), transparent 32rem),
    linear-gradient(180deg, #fbfbfd 0%, var(--fa-bg) 36rem);
}

div[data-testid="stToolbar"],
div[data-testid="stDecoration"] {
  display: none;
}

header[data-testid="stHeader"] {
  background: transparent;
}

.main .block-container,
[data-testid="stMainBlockContainer"] {
  max-width: min(1880px, calc(100vw - 3rem));
  padding-left: 1.5rem;
  padding-right: 1.5rem;
  padding-top: 2rem;
  padding-bottom: 7rem;
}

section[data-testid="stSidebar"] {
  background: rgba(255, 255, 255, 0.82);
  border-right: 1px solid var(--fa-border);
  backdrop-filter: blur(24px) saturate(180%);
}

section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  padding-top: 1.4rem;
}

section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
  display: flex !important;
  position: fixed;
  top: 0.75rem;
  left: 0.75rem;
  z-index: 999999;
  width: 38px !important;
  height: 38px !important;
}

.fa-pdf-document-scroll {
  width: 100%;
  max-height: calc(100vh - 11.5rem);
  overflow: auto;
  padding: 0.65rem;
  border: 1px solid var(--fa-border);
  border-radius: 10px;
  background: #eeeeef;
}

.fa-pdf-page {
  margin: 0 auto 0.9rem;
  padding: 0;
}

.fa-pdf-page:last-child {
  margin-bottom: 0;
}

.fa-pdf-page img {
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.12);
  background: #ffffff;
}

h1, h2, h3, h4 {
  color: var(--fa-text);
  font-family: var(--fa-font);
  letter-spacing: 0;
}

h2, h3 {
  font-weight: 680;
}

p, li, label, span {
  font-family: var(--fa-font);
}

div[data-testid="stMarkdownContainer"] p {
  color: var(--fa-text);
  line-height: 1.58;
}

div[data-testid="stMarkdownContainer"],
div[data-testid="stMarkdownContainer"] li,
div[data-testid="stCaptionContainer"],
div[data-testid="stWidgetLabel"] {
  color: var(--fa-text);
}

.fa-hero {
  border: 1px solid var(--fa-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--fa-shadow);
  padding: 0.85rem 1rem;
  margin: 0.1rem 0 1rem;
  backdrop-filter: blur(20px) saturate(170%);
}

.fa-eyebrow {
  color: var(--fa-blue);
  font-size: 0.72rem;
  font-weight: 700;
  margin-bottom: 0.16rem;
}

.fa-title {
  color: var(--fa-text);
  font-size: clamp(1.65rem, 2.8vw, 2.45rem);
  line-height: 1.05;
  font-weight: 760;
  margin: 0;
  letter-spacing: 0;
}

.fa-subtitle {
  color: var(--fa-muted);
  font-size: 0.92rem;
  max-width: 48rem;
  margin: 0.45rem 0 0.65rem;
}

.fa-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.fa-status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  color: var(--fa-text);
  background: var(--fa-blue-soft);
  border: 1px solid rgba(0, 122, 255, 0.18);
  font-size: 0.86rem;
  font-weight: 600;
}

.fa-section-label {
  color: var(--fa-muted);
  font-size: 0.75rem;
  font-weight: 700;
  margin: 1.25rem 0 0.55rem;
}

div[data-testid="stExpander"] {
  border: 1px solid var(--fa-border);
  border-radius: var(--fa-radius);
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.045);
  overflow: hidden;
}

div[data-testid="stPopoverBody"][data-baseweb="popover"] {
  color: var(--fa-text);
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--fa-border);
  border-radius: 18px;
  box-shadow: 0 22px 48px rgba(0, 0, 0, 0.14);
}

div[data-testid="stPopoverBody"] > div,
div[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
div[data-testid="stPopoverBody"] [data-testid="stVerticalBlockBorderWrapper"] {
  background: transparent !important;
}

div[data-testid="stPopoverBody"] *,
div[data-testid="stPopoverBody"] div[data-testid="stMarkdownContainer"] {
  color: var(--fa-text);
}

div[data-testid="stExpander"] summary {
  min-height: 44px;
  font-weight: 650;
}

.stButton > button,
.stDownloadButton > button,
button[kind="primary"],
button[kind="secondary"] {
  min-height: 44px;
  border-radius: var(--fa-control-radius);
  border: 1px solid var(--fa-border);
  background: rgba(255, 255, 255, 0.92);
  color: var(--fa-text);
  font-weight: 650;
  transition: background 160ms ease, border-color 160ms ease, box-shadow 160ms ease, transform 120ms ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
button[kind="primary"]:hover,
button[kind="secondary"]:hover {
  border-color: rgba(0, 122, 255, 0.42);
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(0, 122, 255, 0.12);
}

.stButton > button:active,
.stDownloadButton > button:active {
  transform: scale(0.99);
}

div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[data-baseweb="select"],
div[data-testid="stFileUploader"] section,
div[data-testid="stChatInput"],
div[data-testid="stChatInput"] textarea,
textarea {
  min-height: 44px;
  border-radius: var(--fa-control-radius);
  border-color: var(--fa-border);
  background: rgba(255, 255, 255, 0.94);
  color: var(--fa-text);
}

div[data-testid="stTextInput"] input:focus,
div[data-testid="stChatInput"] textarea:focus,
textarea:focus {
  border-color: var(--fa-blue);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.18);
}

div[data-testid="stChatInput"] {
  border: 1px solid var(--fa-border);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.08);
}

div[data-testid="stBottom"],
div[data-testid="stBottom"] > div,
div[data-testid="stBottomBlockContainer"] {
  background: linear-gradient(180deg, rgba(245, 245, 247, 0), rgba(245, 245, 247, 0.96) 28%);
}

div[data-testid="stBottom"] {
  left: 336px !important;
  width: calc(100vw - 336px) !important;
}

div[data-testid="stChatInput"] textarea::placeholder {
  color: var(--fa-muted);
}

div[data-testid="stChatMessage"] {
  border-radius: 22px;
  border: 1px solid var(--fa-border);
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.045);
  padding: 0.8rem 1rem;
}

div[data-testid="stAlert"] {
  border-radius: var(--fa-radius);
  border: 1px solid var(--fa-border);
}

hr {
  border-color: var(--fa-border);
}

code {
  border-radius: 7px;
  color: #0f172a;
  background: #eef2ff;
}

@media (max-width: 900px) {
  .main .block-container {
    padding-left: 1rem;
    padding-right: 1rem;
  }

  div[data-testid="stHorizontalBlock"] {
    flex-direction: column;
  }

  div[data-testid="column"] {
    width: 100% !important;
    flex: 1 1 100% !important;
  }

  .fa-hero {
    border-radius: 20px;
    padding: 1.1rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
    animation: none !important;
  }
}
</style>
""".strip()


def app_header_html(*, knowledge_status: str, active_mode: str, course_label: str) -> str:
    safe_status = html.escape(knowledge_status)
    safe_mode = html.escape(active_mode)
    safe_course = html.escape(course_label)
    return f"""
<div class="fa-hero">
  <div class="fa-eyebrow">RAG-Powered Study Assistant</div>
  <h1 class="fa-title">final-agent</h1>
  <p class="fa-subtitle">面向期末复习的本地优先学习工作台，整合课件导入、混合检索、引用校验和 Study Coach 学习闭环。</p>
  <div class="fa-status-row">
    <span class="fa-status-pill">{safe_status}</span>
    <span class="fa-status-pill">当前模式：{safe_mode}</span>
    <span class="fa-status-pill">课程范围：{safe_course}</span>
  </div>
</div>
""".strip()
