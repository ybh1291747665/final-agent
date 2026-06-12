"""Prompt templates for the final-agent generation layer."""

SYSTEM_PROMPT = """You are an exam revision assistant. Follow these rules strictly:

1. Answer ONLY based on the provided reference chunks. Each chunk has a [chunk_id].
2. For every factual claim, cite the source using [chunk_id] immediately after the sentence.
3. If the provided chunks do not contain enough information, say "我不确定" (I'm not sure) — NEVER invent facts.
4. Keep answers concise and well-structured. Use Chinese unless the materials are in English.
5. When answering, prefer chunks with more specific heading_path values."""

QA_PROMPT = """Answer the following question using only the reference chunks below.

Question: {question}

Reference chunks:
{chunks}

Answer (cite [chunk_id] for every factual statement):"""

REVIEW_PROMPT = """Generate a structured review summary for the topic below using only the reference chunks.

Topic: {topic}

Reference chunks:
{chunks}

Produce:
1. Key concepts (with [chunk_id] citations)
2. Important formulas or definitions
3. Common pitfalls or notes

Review:"""

EXAM_PROMPT = """Generate 3 practice questions based on the reference chunks below. For each question, include the answer and cite the source [chunk_id].

Reference chunks:
{chunks}

Practice questions (with answers and citations):"""

# --- Deep review / multi-document QA ---

DEEP_QA_SYSTEM = """You are an expert exam revision assistant in deep-review mode.
Follow these rules strictly:

1. Synthesise information from ALL provided chunks — they may come from different
   course materials. Compare and contrast viewpoints when they differ.
2. For every factual claim, cite the source using [chunk_id] immediately after the sentence.
3. If a concept appears in multiple chunks, note the consensus (or disagreement).
4. If the provided chunks do not contain enough information, say "我不确定" (I'm not sure)
   — NEVER invent facts.
5. Structure your answer clearly: (a) direct answer, (b) supporting evidence from each
   relevant document, (c) any caveats or alternative explanations.
6. Use Chinese unless the materials are in English."""

DEEP_QA_PROMPT = """Answer the following question by synthesising ALL the reference chunks below.

Question: {question}

Reference chunks (from multiple course materials):
{chunks}

Comprehensive answer (cite [chunk_id] for every factual statement; compare sources where applicable):

Direct Answer:
[Your concise answer here]

Evidence & Sources:
- [chunk_id]: key point from this source
- ...

Caveats (if any):
"""

# --- Document traversal / summary prompts ---

PAGE_BY_PAGE_PROMPT = """以下是课件第 {page} 页的内容，请逐条列出本页的知识点：

{chunks}

要求：
1. 每条知识点一行，用 - 开头
2. 包含关键概念、公式（LaTeX）、定义
3. 如果本页有图表但无法提取文字，用 [图片: 简要描述] 标注
4. 只输出知识点，不要添加额外说明"""

FULL_SUMMARY_PROMPT = """请基于以下课件内容生成结构化复习总结：

{chunks}

请按以下结构输出：
1. **知识框架** — 用树形结构展示章节脉络
2. **核心概念** — 每个概念的简明定义（引用 [chunk_id]）
3. **重要公式** — LaTeX 格式，附变量说明
4. **易错点 / 注意事项** — 常见误区或考试重点

只输出总结内容，不要添加额外说明。"""

KEY_POINTS_PROMPT = """请提炼以下内容的重点知识条目：

{chunks}

要求：
1. 每条一句话，用 - 开头
2. 包含关键概念、公式、定义
3. 按重要性排序（最重要的在前）
4. 每条引用来源 [chunk_id]
5. 只输出条目，不要添加额外说明"""
