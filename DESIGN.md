# final-agent — 期末复习 RAG Agent

> 基于 RAG（检索增强生成）的智能复习助手。上传 PDF / Markdown 课件，自动解析、分块、向量化，通过混合检索 + DeepSeek 生成带引用标注、防幻觉的复习解析。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                         Streamlit UI                             │
│  📂 上传课件  │  🔑 API 配置  │  📚 课程选择  │  🔍 五模式切换    │
│  💬 多对话   │  📄 知识库管理  │  幻觉可视化  │  引用来源展示     │
└──────────────────────────────┬───────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
   ┌──────────┐     ┌──────────────┐      ┌──────────────────┐
   │ Ingestion│     │  Retrieval   │      │   Generation     │
   │          │     │              │      │                  │
   │ Doubao   │     │ Query Expand │      │  QA (standard)   │
   │ API VLM  │     │      │       │      │  Deep QA         │
   │    │     │     │      ▼       │      │  Summarizer      │
   │    ▼     │     │ Hybrid Search│      │  (3 modes)       │
   │ Chunker  │     │  (RRF k=60)  │      │        │         │
   │ (+page)  │     │      │       │      │        ▼         │
   │    │     │     │      ▼       │      │  LLM Client      │
   │    ▼     │     │  Reranker    │      │  (DeepSeek)      │
   │ 🖼️ VLM  │     │      │       │      │        │         │
   │ Analyzer │     │      ▼       │      │        ▼         │
   │          │     │  Filter      │      │  Guard (L2)      │
   └────┬─────┘     │      │       │      └──────────────────┘
        │           │      ▼       │
        │           │ deep_search  │
        │           │ (+neighbor)  │
        │           └──────┬───────┘
        │                  │
        └────────┬─────────┘
                 ▼
         ┌──────────────┐
         │  Knowledge   │
         │              │
         │ ChromaDB     │ ← dense vectors (cosine)
         │ BM25 + JSON  │ ← sparse index (jieba)
         │ Metadata     │ ← doc registry (+course_id)
         └──────────────┘
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| PDF 解析 | **豆包 Doubao-Seed-2.0-Pro** (火山方舟 VLM) | pypdfium2 渲染页码→API 逐批提取 Markdown |
| 备选解析 | **MinerU 3.3** (pipeline) | 保留代码，可选依赖，CPU OCR + 布局 |
| 图片理解 | **豆包 Doubao-Seed-2.0-Pro** (火山方舟) | 可选，API 接入 |
| 嵌入模型 | **BAAI/bge-large-zh-v1.5** | 1024 维，sentence-transformers 本地加载 |
| 向量库 | **ChromaDB** | 持久化，cosine 距离 |
| 稀疏检索 | **BM25Okapi** + **jieba** | JSON 词项-文档矩阵持久化 |
| 重排序 | **BAAI/bge-reranker-v2-m3** | Cross-encoder 精排 |
| 生成模型 | **DeepSeek V4 Pro** | OpenAI 兼容 API |
| 防幻觉 | **bge-reranker** L2 语义校验 | 逐句 cross-encoder 相似度，阈值 0.3 |
| UI | **Streamlit** | typer CLI + Web UI |
| 环境 | **Anaconda** (final-agent) | Python 3.11 |

---

## 数据流

### 导入流程

```
PDF 文件
  │
  ▼
doubao_parser.py
  │  pypdfium2 每页渲染为 PNG (200 DPI) → base64
  │  豆包 VLM API 逐批（3 页/批）提取 Markdown → 拼接
  │  产出: Markdown 到 data/markdown/<stem>/<stem>.md
  │
  ▼
image_analyzer.py (可选 — 勾选后启用)
  │  扫描 ![](images/xxx.png) → base64 → 豆包 VLM API
  │  图片描述注入 Markdown
  │
  ▼
chunker.py
  │  按 ##/###/#### 标题层级分块
  │  超长段落按句号递归子分块 + overlap
  │
  ▼
embedder.py → ChromaDB.add  (dense)
  │         → BM25.build    (sparse → bm25_index.json)
  │         → metadata.register
  │
  ▼
知识库就绪
```

### 问答流程

```
用户问题
  │
  ▼
query_expander (jieba 分词 + 同义词扩展)
  │
  ├──→ ChromaDB.query  (dense)  ──┐
  └──→ BM25.search     (sparse) ──┤ ThreadPoolExecutor 并行
                                   │
  ▼                                ▼
RRF (Reciprocal Rank Fusion, k=60) ← 融合排名
  │
  ▼
bge-reranker 精排 (cross-encoder)
  │
  ▼
filter (similarity_threshold + min_matches)
  │
  ▼
DeepSeek V4 Pro 生成 + 引用注入 [chunk_id]
  │
  ▼
Guard (L2): 逐句 cross-encoder 校验引用语义一致度
  │  低于 0.3 → ⚠️ 标记疑似幻觉
  │
  ▼
输出: 带引用标注的答案 + 幻觉标记 + 来源 chunk 可查看
```

### 深度问答流程 (deep)

```
用户问题
  │
  ▼
query_expander → hybrid_search (高召回: review_top_k × 3)
  │
  ▼
reranker 精排 → filter (低阈值: review_similarity_threshold)
  │
  ▼
邻居扩展 (neighbor_expand=2): 前后相邻 chunk 补上下文
  │
  ▼
同 heading 去重 (最多 2 个/heading_path)
  │
  ▼
DeepSeek V4 Pro 生成 (DEEP_QA_SYSTEM: 多文档综合 / 对比)
  │
  ▼
输出: 综合答案 + 逐来源引用 + 跨文档对比
```

### 文档遍历总结流程 (summarizer)

```
用户选择 模式 + 目标文档
  │
  ▼
summarizer.py
  │  chroma_get_chunks_by_doc → 按 page_num 或 char_start 排序
  │  分批 (max_chunks_per_batch=20, 按 max_tokens 估算窗长)
  │  每批 LLM 调用 (temperature=0.3)
  │
  ├── page_by_page  → PAGE_BY_PAGE_PROMPT → "## 第N页" 逐页输出
  ├── full_summary  → FULL_SUMMARY_PROMPT → 知识框架+概念+公式+易错点
  └── key_points    → KEY_POINTS_PROMPT   → 重点条目列表
```

---

## 目录结构

```
final-agent/
├── main.py                     # CLI 入口 (ingest/ask/review/ui)
├── config.yaml                 # 模型/分块/检索/向量库/图片分析配置
├── .env.example                # API Key 模板 (DeepSeek + 火山方舟)
├── pyproject.toml              # Python 项目配置
├── interviewer-note.md         # 决策记录 + 错误日志
├── DESIGN.md                   # 本文件
│
├── data/
│   ├── uploads/                # 上传的原始文件
│   ├── markdown/               # PDF 解析输出的 Markdown
│   ├── images/                 # PDF 提取的图片
│   ├── chunks/                 # (预留)
│   ├── vector_db/              # ChromaDB 持久化 + bm25_index.json
│   └── models/                 # MinerU 模型缓存 (3-5 GB)（可选）
│
└── src/final_agent/
    ├── main.py                 # typer CLI
    ├── schemas.py              # Chunk / ScoredChunk / GeneratedAnswer 等
    ├── settings.py             # Pydantic + YAML 配置加载
    │
    ├── ingestion/              # Phase 2: PDF → Chunks
    │   ├── pdf_parser.py       #   MinerU CLI 子进程（保留，可选依赖）
    │   ├── doubao_parser.py    #   Doubao API PDF 解析（主力）
    │   ├── image_analyzer.py   #   VLM 图片分析 (豆包 API)
    │   ├── chunker.py          #   标题感知 + 递归子分块
    │   └── importer.py         #   统一入口
    │
    ├── knowledge/              # Phase 3: 向量化 + 索引
    │   ├── embedder.py         #   BGE 嵌入 (sentence-transformers)
    │   ├── vector_store.py     #   ChromaDB 客户端 (cosine)
    │   ├── bm25_index.py       #   BM25 + jieba + JSON 持久化
    │   ├── metadata.py         #   文档元数据
    │   └── builder.py          #   统一 build(chunks) 入口
    │
    ├── retrieval/              # Phase 4: 混合检索
    │   ├── query_expander.py   #   jieba 分词 + 同义词
    │   ├── hybrid_searcher.py  #   RRF 融合 + 并行检索
    │   ├── reranker.py         #   bge-reranker 精排
    │   ├── filter.py           #   阈值过滤
    │   └── pipeline.py         #   串联入口
    │
    ├── generation/             # Phase 5: 生成 + 防幻觉 + 总结
    │   ├── prompts.py          #   QA/Review/Exam/DeepQA/Summary 模板
    │   ├── llm_client.py       #   OpenAI 兼容客户端 + stream
    │   ├── answer_generator.py #   答案生成 + citation 提取 (qa/deep)
    │   ├── summarizer.py       #   文档遍历式总结 (3 种模式)
    │   └── guard.py            #   L2 防幻觉 (cross-encoder)
    │
    └── ui/                     # Phase 6: 界面
        └── app.py              #   Streamlit (多对话/知识库/幻觉可视化)
```

---

## 关键架构决策

| # | 决策 | 选择 | 原因 |
|---|------|------|------|
| 1 | PDF 解析 | MinerU CLI 子进程 → **Doubao VLM API** (Phase 7) | MinerU 太慢，全面切换为纯 API 方案，MinerU 代码保留为可选依赖 |
| 2 | 分块策略 | 标题感知 + 递归子分块 | 保留 Markdown 语义边界，超长段落逐句切分 |
| 3 | Chunk schema | 跨模块 Pydantic 数据契约 | Phase 2-5 五个模块统一数据结构 |
| 4 | BM25 持久化 | JSON 词项-文档矩阵 | 重启无需 re-tokenize，版本无依赖 |
| 5 | ChromaDB | PersistentClient + cosine | 本地持久化 + cosine hnsw:space |
| 6 | 混合检索融合 | RRF (k=60) | BM25 分数和余弦相似度不同量级，RRF 只关心排名 |
| 7 | Rerank 位置 | 融合后精排 | RRF 粗筛 → reranker 精排，经典两阶段 |
| 8 | 并行检索 | ThreadPoolExecutor(max_workers=2) | Dense 和 Sparse 互不依赖 |
| 9 | 防幻觉 | L2 语义一致性校验 | bge-reranker 逐句校验引用句子与 chunk 相似度 |
| 10 | CLI | typer | 利用已有 Pydantic，代码量最少 |
| 11 | Streamlit 状态 | st.cache_resource + AppState | 重型资源缓存，会话级 Pydantic 模型 |
| 12 | 多对话 | AppState.conversations dict | 每个对话独立 history，支持切换/新建/删除 |
| 13 | VLM 图片分析 | 外部 API（豆包 Doubao） | 不依赖本地 GPU，API 统一管理 |
| 14 | 模型下载 | ModelScope 国内镜像 | Windows 无需管理员权限，无 symlink 问题 |
| 15 | PDF 解析全面切换 | Doubao VLM API 替代 MinerU | MinerU 本地解析太慢；pypdfium2 渲染 + 豆包 API 逐批提取 Markdown，3 页/批，ThreadPoolExecutor 并行 |
| 16 | 五模式复习体系 | QA / 深度问答 / 逐页输出 / 全文总结 / 重点总结 | RAG 检索 + 文档遍历式生成互补，覆盖精准问答到全面复习 |
| 17 | 课程分组 | 单知识库 + course_id 过滤 | ChromaDB where $in + BM25 后置过滤，零额外 Collection 开销 |

---

## 使用方式

```bash
conda activate final-agent

# CLI 模式
final-agent ingest lecture.pdf       # 导入课件
final-agent ask "如何理解导数？"      # 提问
final-agent review --topic 微积分     # 复习总结

# Web UI
final-agent ui                        # 浏览器打开 http://localhost:8501
```

### Web UI 功能

| 区域 | 功能 |
|------|------|
| 🔑 API 配置 | DeepSeek Key + 豆包 Key，自动写入 `.env` |
| 🖼️ 图片分析 | 勾选启用 → 上传 PDF 时自动用豆包分析图片内容 |
| 📚 课程 | 下拉选择课程范围（全部课件 / 指定课程），导入时自动分组 |
| 🔍 检索设置 | 模式切换：问答 / 深度问答 / 逐页输出 / 全文总结 / 重点总结 |
| 💬 对话 | 多对话管理（新建/切换/删除/自动命名） |
| 📄 知识库 | 文档列表 + chunk 数 + 🔍查看 chunk + 🗑️删除文档 |
| 💬 问答区 | 答案 + 幻觉检测 (✅/⚠️) + 逐句校验详情 + 引用 chunk 可查看 |

### 五种复习模式

| 模式 | 检索方式 | 适用场景 |
|------|---------|---------|
| 🔍 **问答** (qa) | hybrid→rerank→filter→LLM | 精准提问：某概念的定义、公式推导 |
| 📖 **深度问答** (deep) | 高召回 + 邻居扩展 + 多文档综合 | 期末复习：跨课程对比、综合论述 |
| 📄 **逐页输出** (page_by_page) | 按 page_num 遍历全文档 | 课前预习：逐页提取知识点 |
| 📋 **全文总结** (full_summary) | 全量 chunk 分批 LLM | 总复习：结构化框架+概念+公式 |
| ⭐ **重点总结** (key_points) | 全量 chunk 分批 LLM | 考前突击：重点条目提炼 |
