# Interviewer Note — final-agent 项目决策记录

> 记录所有重大决策、决策原因、遇到的错误和解决方法。

---

## Phase 1 — 项目脚手架初始化

- **Anaconda 管理虚拟环境**: 用户指定 conda，放弃 uv/venv
- **MinerU PDF 解析**: 国产开源、中文最优、hybrid 引擎，替代 Marker/Docling
- **DeepSeek V4 Pro 生成模型**: 用户指定，openai 兼容 API
- **mattpocock/skills 工程技能集**: 29 skills 安装到 .agents/skills/
- **依赖管理**: pyproject.toml + pip install -e ".[dev]"

## Phase 2 — PDF 解析与 Markdown 导入

- **Chunk schema 跨模块契约**: schemas.py 定义 Chunk/ScoredChunk/GeneratedAnswer/HallucinationFlag/VerifiedAnswer
- **MinerU CLI 子进程**: 隔离 torch 依赖，避免与 sentence-transformers 冲突
- **标题感知 + 递归子分块**: 按 ##/###/#### 切逻辑节，超长节按句号递归子分块 + overlap，空节/不同 heading_path 不合并
- **min_chunk_chars = 20**: 防止 48-char sub-chunk 被误合并

## Phase 3 — 知识库构建

- **BM25 JSON 词项-文档矩阵持久化**: 重启后从 JSON 还原 BM25Okapi 内部状态，无需 re-tokenize
- **ChromaDB cosine space**: hnsw:space=cosine，与 normalize_embeddings 搭配
- **嵌入模型全局缓存**: SentenceTransformer 加载耗时，模块级缓存复用

## Phase 4 — 混合检索与重排序

- **RRF (Reciprocal Rank Fusion)**: 融合 dense+sparse 排名，规避分数量级差异，k=60
- **融合后 rerank**: RRF 取 top_k*3 → cross-encoder 精排 → filter，经典两阶段
- **ThreadPoolExecutor 并行**: dense 和 sparse 检索同时提交，减半延迟

## Phase 5 — 生成与防幻觉

- **L2 防幻觉**: bge-reranker 逐句校验引用句子与 chunk 语义相似度，阈值 0.3
- **三种 prompt 模板**: QA（逐句引用）/ Review（结构化摘要）/ Exam（模拟题）

---

## Phase 6+ — 读图能力、知识库可见性、反幻觉可视化

### 决策：VLM 图片分析走外部 API（方案 B，非 MinerU 内置）

- **决策原因**: 统一走 API 管理，不依赖本地 GPU；用户可自由切换模型
- **模型选择**: 最终使用 **豆包 Doubao-Seed-2.0-Pro**（火山方舟 Ark），替代最初考虑的 Qwen-VL
- **原因**: 用户指定，视觉能力强，价格实惠
- **接入**: `ARK_API_KEY` + `ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`，OpenAI 兼容格式

### 新增文件

- `ingestion/image_analyzer.py`: 扫描 MinerU 输出的 Markdown，正则匹配 `![](path)`，base64 编码图片，调 OpenAI 兼容 VLM API，返回描述注入 Markdown
- `config.yaml` vision 段: enabled/provider/model/api_key/base_url/max_images_per_doc/prompt
- `settings.py` VisionSettings: 独立配置模型，`_sanitize_vlm()` 防御 None

### UI 增强

- **侧边栏 API 配置**: DeepSeek + Qwen-VL 两个独立面板，输入即写入 `.env`
- **侧边栏知识库**: 显示已导入文档列表 + chunk 数 + 来源路径 + 导入时间
- **答案区幻觉可视化**: 每条引用标注 ✅/⚠️ + 相似度分数 + 逐句校验详情
- **答案区引用来源**: 展开显示每个 chunk 的 heading_path + 完整文本 (400 chars) + 检索分数

---

## 错误记录

| 日期 | 错误 | 原因 | 解决方法 |
|------|------|------|----------|
| 2025-06-11 | uv 命令不可用 | uv 未安装 | 使用 conda |
| 2025-06-11 | && 语法报错 | PowerShell 不支持 && | 改用 ; |
| 2025-06-11 | write_file sandbox 拒绝 | workspace 限制 | bash Out-File |
| 2025-06-11 | delete_range 截断函数签名 | 匹配过头 | 重写 chunker.py |
| 2025-06-11 | chunker 167 chars (预期 103) | \r\r\n 双重 CRLF | replace('\r\n','\n').replace('\r','') |
| 2025-06-11 | 空 \n 导致 overlap 错误 | buffer.strip()="" 仍 truthy | buffer.strip() 判断 |
| 2025-06-11 | UTF-8 BOM 标题不匹配 | Set-Content 加 BOM | 读取时跳过 BOM |
| 2025-06-11 | 硬切分 3-char 尾部碎片 | overlap 步长 | chunk_size 步长 + 尾部合并 |
| 2025-06-11 | conda run 中文乱码 | GBK 编码 | PYTHONIOENCODING=utf-8 |
| 2025-06-11 | chromadb l2 distance | 未设 hnsw:space | hnsw:space=cosine |
| 2025-06-11 | _sparse_retrieve missing settings | ThreadPoolExecutor 传参 | Optional 默认值 |
| 2025-06-12 | Streamlit `final-agent ui` 空白页 | @st.cache_resource 里 bm25_load([], …) 在空知识库时崩溃；`data/uploads` 相对路径 Streamlit 解析失败 | try/except 包裹初始化，路径改为基于 Path(__file__).resolve() 的绝对路径，所有环节加错误提示 |
| 2025-06-12 | 用户需手动编辑 .env 填 API Key | 没有界面入口 | Streamlit 侧边栏添加 API Key 输入框，实时写入 .env 并更新 settings |
| 2025-06-12 | `LLMSettings.api_key` 验证失败 "不能是 None" | config.yaml 中 `api_key: ${DEEPSEEK_API_KEY}` 未配 env 时 YAML 解析为 `null`，Pydantic `str` 类型拒绝 | config.yaml 改为 `${DEEPSEEK_API_KEY:-}`；settings.py 新增 `_sanitize_llm()` 防御性地 None→"" |
| 2025-06-12 | write_file 写入 app.py 带 UTF-8 BOM 导致语法错误 | write_file 工具默认写 BOM | PowerShell 检测并剔除 BOM 字节 (`0xEF 0xBB 0xBF`) |
| 2025-06-12 | 上传第二篇 PDF 卡死 + BM25 覆盖 | ① `st.cache_resource.clear()` 触发 Streamlit 重跑→spinner 永不消失；② `build_index` 全量覆盖旧 chunk | ① clear() 替换为 `build_counter` 计数器→`_h` 参数自然失效；② `builder.py` merge 旧 chunk + 新 chunk 后调用全量 build_index；③ file_uploader 加动态 key 防残留触发 |
| 2025-06-12 | `Path.resolve()` 解析到 System32 | Streamlit subprocess CWD 是 Windows System32 | `settings.py` load_settings 中 `_resolve_paths()` 将所有 data 路径转为 `project_root` 前缀的绝对路径 |
| 2025-06-12 | MinerU hybrid-engine 报错 `CUDA is not available` | 当前机器无 NVIDIA GPU | `pdf_parser.py` 默认 backend 从 `hybrid-engine` 改为 `pipeline`（纯 CPU 可用） |
| 2025-06-12 | MinerU pipeline 报错 `WinError 1314`（客户端没有所需的特权） | Windows 非管理员用户无法创建 symlink，HuggingFace Hub 默认用 symlink 管理缓存 | **最终方案：切换到 ModelScope**。通过 `MINERU_MODEL_SOURCE=modelscope` 环境变量，MinerU 走阿里 ModelScope 国内镜像下载模型（直接 HTTP 下载，无需 symlink） |
| 2025-06-12 | ModelScope 首次下载模型不完整（MFR 公式识别权重缺失） | `snapshot_download` 断点续传不稳定，MFR 子目录只有 config.json 没有 .pth/onnx 权重文件 | 清理缓存后重新 `snapshot_download("opendatalab/PDF-Extract-Kit-1.0")`，确保 models/MFR 下所有权重文件完整下载 |
| 2025-06-12 | DeepSeek API 401 认证失败，报错 key `****adb1` 不匹配 | `_CLIENT_CACHE` 缓存的旧 OpenAI 客户端永不更新；`_sanitize_ascii` 过滤可能截断 key | 去掉 llm_client 缓存（每次从 settings 创建新客户端）；settings.py `_env_var` 新增 .env 文件直接读取回退 |
| 2025-06-12 | `\uff1a` UnicodeEncodeError (全角冒号) | API Key/URL 中混入全角字符，HTTP 头部仅支持 ASCII | settings.py 新增 `_fixup_ascii()` 全角→半角转换 |
| 2025-06-12 | BM25 index not loaded | `ensure_knowledge_loaded` 传空列表 `[]` 给 `bm25_load` → `build_index([])` 清空缓存并删 JSON | vector_store 新增 `get_all_chunks()`；UI 从 ChromaDB 取全量 chunk 恢复 BM25 |
| 2025-06-12 | 豆包模型配置错误 | 模型名 `doubao-seed-2.0-pro` 不存在 | 改为 `doubao-seed-2-0-pro-260215`（pro）/ `doubao-seed-2-0-lite-260428`（lite） |
| 2025-06-12 | 对话历史关闭浏览器后丢失 | `AppState` 仅存在 `st.session_state` 内存中 | 新增 `_save_conversations`/`_load_conversations`，JSON 持久化到 `data/conversations.json` |
| 2025-06-12 | Pydantic V2 `class Config` 弃用警告 | 旧版写法 | 改为 `model_config = ConfigDict(arbitrary_types_allowed=True)` |
| 2025-06-12 | write_file 每次写入带 UTF-8 BOM 导致 SyntaxError | 工具默认写 BOM | 每次编辑后 PowerShell 检测 `0xEF 0xBB 0xBF` 并剔除 |
| 2025-06-12 | QA 检索只返回 2-3 个 chunk，无法覆盖整份课件 | 语义搜索 top_k=10 只召回最相似内容 | Phase 8 新增 deep_search（高召回 + 邻居扩展 + 去重）和 summarizer（全量文档遍历） |
| 2025-06-12 | 多门课程混在一起检索不精准 | 所有文档在同一个知识库，检索跨课程污染 | Phase 8 新增 `course_id` 分组 + ChromaDB where 过滤 + BM25 后置过滤 |

## MinerU 模型缓存说明

- **ModelScope 默认位置**: `~/.cache/modelscope/hub/opendatalab/PDF-Extract-Kit-1.0/`
- **本项目重定向**: `data/models/`（通过 `MODELSCOPE_CACHE` 环境变量）
- **模型来源**: `MINERU_MODEL_SOURCE=modelscope` → 走阿里 ModelScope 国内镜像（HTTP 直下，无需 symlink，不需要管理员权限）
- **模型大小**: 约 3-5 GB，含 Layout/OCR/MFR/TabRec/TabCls/OriCls/ReadingOrder 七个子模块
- **MinerU 与豆包 VLM 的关系**: 不冲突。MinerU 负责 "PDF → Markdown + 导出图片"（本地 CPU 模型，不需 API）；豆包负责 "理解图片语义内容"（可选勾选，调火山方舟 API）

## Phase 7 — PDF→Markdown Doubao 纯 API 方案（替代 MinerU）

### 决策：全面切换为 Doubao VLM API PDF 解析

- **决策原因**: MinerU 本地解析太慢，用户倾向纯 API 方案；豆包 API Key 已配置，无需额外基础设施
- **实现**: pypdfium2 渲染 PDF 每页为 PNG（200 DPI）→ base64 → 豆包 API 逐批（3 页/批）提取 Markdown → 拼接为完整 .md
- **MinerU 处理**: 代码保留（`pdf_parser.py`），改为可选依赖 `pip install -e ".[mineru]"`；不再参与默认运行流程
- **新增文件**: `ingestion/doubao_parser.py`
- **修改文件**: `importer.py`（PDF 路径改为调用 doubao_parser）、`config.yaml`（vision 段新增 page_dpi/max_pages/pages_per_batch）、`settings.py`（VisionSettings 新增对应字段）、`pyproject.toml`（mineru→可选依赖，新增 pypdfium2）
- **UI**: 上传 PDF 时快速统计页数并显示「共 N 页（处理前 M 页），将分 X 批调用 Doubao API 解析」

### 批次策略

- **3 页/批**: 利用跨页上下文（跨页段落/表格不被切断），比逐页质量更好；失败范围可控
- **200 DPI**: 清晰度与 token 消耗的平衡点
- **max_pages=100**: 单文档上限，防止超长 PDF 费用失控

### 依赖变更

- 默认安装不含 mineru[all]（约 3-5 GB 模型）：`pip install -e "."`
- 需要 MinerU 时手动安装：`pip install -e ".[mineru]"`

### 并行加速

- **问题**: 串行调用 API，30 页 PDF = 10 批次 × 10-15s = 100-150s
- **方案**: ThreadPoolExecutor 并行发出所有批次，`concurrent_batches=5`（可配置）
- **效果**: 30 页 PDF 从 ~120s → ~20s（渲染 ~2s + API ~18s），接近 6x 加速
- **实现**: `doubao_parser.py` Phase 1 预渲染所有页面为 PNG → Phase 2 `concurrent.futures` 并行调 API → Phase 3 按页码顺序拼接

## Phase 8 — 多模式复习体系 + 课程分组 + 页面追踪

### 决策：从纯 RAG 扩展到五大复习模式

- **决策原因**: 纯语义检索只能回答精准问题，无法做"逐页输出知识点""全文总结"等文档遍历式操作
- **五种模式**:
  - `qa` — 现有 RAG 检索（hybrid→rerank→filter→LLM），适合精准提问
  - `deep` — 高召回+邻居扩展+多文档综合，适合跨课程深度问答
  - `page_by_page` — 按 page_num 分组，逐页 LLM 提取知识点
  - `full_summary` — 全量 chunk 分批 LLM，输出结构化复习总结
  - `key_points` — 同上，prompt 侧重概念/公式/易错点提炼
- **新增文件**: `generation/summarizer.py`、`prompts.py` 新增 5 个模板
- **修改文件**: `pipeline.py`（新增 deep_search）、`answer_generator.py`（新增 answer_deep）
- **UI**: 侧边栏新增模式选择器；聊天区根据模式分支到不同生成路径

### 决策：课程分组（单知识库 + 过滤）

- **决策原因**: 多门课程混在一个知识库会导致检索不精准；但多 Collection 管理复杂
- **实现**: Chunk + metadata 新增 `course_id`；检索时 ChromaDB `where` $in + BM25 后置过滤
- **UI**: 上传时自动按课程分组，侧边栏下拉切换课程范围

### 决策：页面追踪

- **实现**: doubao_parser 每批 Markdown 前插入 `<!-- page_start: N -->`；chunker 解析后填入 `Chunk.page_num`
- **用途**: `page_by_page` 模式按页码分组输出知识点

### 配置扩展

- `retrieval` 段新增 `review_top_k` / `review_similarity_threshold` / `neighbor_expand`
- 后续可加 `summary` 段（`max_chunks_per_batch`、`temperature`）

## Phase 9 — Flash/Pro 按模式切换 + 幻觉饼图

### 决策：五种模式各自独立选择 DeepSeek 模型

- **决策原因**: 不同复习场景对生成质量/速度/成本的需求不同。QA 需要精准（Pro），总结可以省钱加速（Flash）。如果全局统一切换，用户每次切换模式还要记得手动换模型；按模式独立记忆更符合直觉
- **两种模型**:
  - `deepseek-v4-flash` — 轻量快速，适合总结、逐页输出
  - `deepseek-v4-pro` — 高精度推理，适合复杂问答、跨文档对比
- **UI**: 检索设置区「模  式」下拉框下方新增 `⚡ 模型选择` radio（横向排列 Flash / Pro），切换模式时 radio 自动反映该模式的当前选择
- **持久化**: 存入 `conversations.json` 的 `model_prefs` 字段，重启不丢失；默认全部为 Flash
- **传递路径**: `app.py` → `answer_question()` / `answer_deep()` / `summarize_document()` → `llm_client.generate()` 的 `model=` 参数
- **修改文件**: `ui/app.py`（AppState + radio + 传参）、`answer_generator.py`（`answer_question` / `answer_deep` 加 `model` kwarg）、`summarizer.py`（`summarize_document` / `_summarize_by_page` / `_summarize_full` 加 `model` kwarg）
- **为何不用 .env 或 config.yaml**: 这是 UI 运行时偏好而非环境配置；与 `course_id`/`query_mode` 同属会话级 UI 状态，放 `conversations.json` 一文件管理

### 决策：侧边栏幻觉校验饼图

- **决策原因**: 主区域已有逐句 ✅/⚠️ 详情，但用户需要一个"宏观视角"一眼看到当前会话的整体幻觉率。饼图直观展示比例，切换对话即切换统计范围（对话级统计而非全局）
- **数据来源**: 遍历当前对话 `history` 中所有 assistant 消息的 `flags` 字段，汇总 `flagged==True`（疑似）和 `flagged==False`（通过）
- **渲染**: matplotlib `pie()`，绿色 ✅通过 / 红色 ⚠️疑似；全部通过时只显示绿色扇区
- **交互**: 放在对话列表下、检索设置上的 `📊 幻觉统计` expander，默认展开
- **空态**: 当前对话无校验数据时显示「📭 当前对话暂无校验数据」
- **统计范围为何是当前对话而非全局**: 不同对话可能对应不同课程，幻觉率差异大；全局混合失去诊断意义。用户可通过切换对话查看各门课的幻觉表现

## Phase 10 — Adaptive Study Coach Agent

### Issue: Phase 0 盘点与单 Agent 路线确认

- **Date:** 2026-06-20
- **Status:** resolved
- **Where:** `final-agent-ai-worker-guide.md`, `docs/superpowers/plans/2026-06-13-adaptive-study-coach-agent.md`
- **Symptom:** 需要把项目从 RAG 复习助手升级为可测试的自适应学习 Coach，同时当前 worktree 已有未提交改动。
- **Root cause:** Agent 改造计划跨度大，必须先保留现有 RAG 层和未提交工作，避免直接重写。
- **Options considered:**
  - Option A: 直接重写为完整 Agent，速度快但容易破坏现有 RAG。
  - Option B: 保留 RAG 知识层，在外层增加一个有边界的单 Agent 工作流，测试更稳定。
- **Decision:** 选择 Option B。第一版不做多 Agent，使用确定性 planner、typed tools、SQLite memory 和 FastAPI sessions。
- **Fix:** 新增 `agent/`, `memory/`, `api/`, `evaluation/` 模块和离线测试；保留原有 ingestion/retrieval/generation/UI 结构。
- **Verification:** `pytest tests/test_schemas.py tests/retrieval tests/ingestion tests/evaluation tests/agent tests/memory tests/api tests/ui -q`
- **Result:** 22 passed，存在 FastAPI/httpx 第三方弃用警告。
- **Resume impact:** can mention after measured

### Issue: 离线测试被重依赖导入阻塞

- **Date:** 2026-06-20
- **Status:** resolved
- **Where:** `bm25_index.py`, `query_expander.py`, `vector_store.py`, `embedder.py`, `reranker.py`, `guard.py`
- **Symptom:** 新增测试首次运行时缺少 `jieba`, `rank_bm25`, `chromadb`, `sentence_transformers` 导致 import 阶段失败。
- **Root cause:** 旧知识层在模块顶层直接导入重依赖，不符合“单元测试不要求模型下载/外部服务”的计划约束。
- **Options considered:**
  - Option A: 在测试环境安装所有依赖，接近真实运行但慢且脆弱。
  - Option B: 对重依赖做惰性导入或轻量 fallback，让测试只覆盖当前层逻辑。
- **Decision:** 选择 Option B。真实 embedding/vector/rerank 功能在调用时仍要求安装依赖，离线测试不触发。
- **Fix:** 为 BM25/query expansion 增加轻量分词 fallback；为 Chroma、embedding、reranker、hallucination guard 增加缺依赖时的延迟 RuntimeError。
- **Verification:** `pytest tests/test_schemas.py tests/retrieval tests/ingestion tests/evaluation tests/agent tests/memory tests/api tests/ui -q`
- **Result:** 22 passed。
- **Resume impact:** none

### Issue: evaluation runner 命令首次找不到包

- **Date:** 2026-06-20
- **Status:** resolved
- **Where:** `python -m final_agent.evaluation.runner --suite baseline`
- **Symptom:** `ModuleNotFoundError: No module named 'final_agent'`。
- **Root cause:** 当前 shell 没有执行 editable install，也没有设置 `PYTHONPATH=src`。
- **Options considered:**
  - Option A: 立即运行 `pip install -e ".[dev]"`，更贴近用户安装路径但会改动本机环境。
  - Option B: 使用 `$env:PYTHONPATH='src'` 复跑，适合当前工作区验证。
- **Decision:** 选择 Option B 作为本轮验证方式；README 仍记录标准 `pip install -e ".[dev]"`。
- **Fix:** 用显式 `PYTHONPATH=src` 复跑 baseline 和 agent-final evaluation。
- **Verification:** `$env:PYTHONPATH='src'; python -m final_agent.evaluation.runner --suite baseline; python -m final_agent.evaluation.runner --suite agent-final`
- **Result:** 生成 `data/evaluation/baseline.json` 和 `data/evaluation/agent-final.json`。
- **Resume impact:** none

### Issue: `agent-final` evaluation 需要真实课件证据

- **Date:** 2026-06-20
- **Status:** resolved
- **Where:** `src/final_agent/evaluation/dataset.py`, `src/final_agent/evaluation/runner.py`
- **Symptom:** 旧 `agent-final` report 只复制 fixture citation，不能回答“Agent 是否真的用本地课件跑过”。
- **Root cause:** v1 evaluation 为了离线稳定，最初只覆盖固定 fixture；这适合 CI，但证据不够接近真实 course material。
- **Options considered:**
  - Option A: 直接调用 live LLM + Chroma/Reranker，全链路真实但需要 API key、模型和本地向量库，CI 不稳定。
  - Option B: 读取 `data/markdown`，复用 page-aware chunker，生成本地课程 case，并用确定性词法检索计算 citation grounding。
- **Decision:** 选择 Option B 作为本轮“真实 evaluation runner”。它验证真实本地 Markdown chunk/citation 路径，不声明 live LLM 或生产检索质量。
- **Fix:** `agent-final` 在有 `data/markdown` 时生成 `local-*` cases，并通过确定性 local search adapter 运行 Agent workflow；无本地 Markdown 时回退 fixture，保证自动测试不依赖重数据。
- **Verification:** `$env:PYTHONPATH='src'; python -m final_agent.evaluation.runner --suite agent-final --data-dir data`
- **Result:** 30 cases；task completion 100%；tool-selection 100%；citation-grounding 66.7%；grading agreement 100%；error rate 0%。
- **Reworked check:** `ruff check src tests` 因当前 shell PATH 找不到 `ruff` 失败；改用 `python -m ruff check src tests`，结果通过。
- **Resume impact:** can mention local-course evaluation evidence, but say no live LLM quality claim

### Issue: Study Coach UI 缺少 mastery / next action / tool trace 证据字段

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `src/final_agent/ui/app.py`, `src/final_agent/ui/study_coach_view.py`, `src/final_agent/api/schemas.py`
- **Symptom:** 手工 demo 前，Study Coach 模式只显示 status、plan、question、grade，和 guide 里要求的 mastery visibility、next action、tool trace visibility 不完全一致。
- **Root cause:** Session API 未显式返回 `next_action`，UI 也没有继续请求 mastery/trace；同时 `ui/app.py` 导入即执行整页 Streamlit，直接在该文件上做渲染单测会把测试和页面生命周期绑死。
- **Options considered:**
  - Option A: 保持现状，在 evidence 文档里解释 UI 省略这些字段。
  - Option B: 先补齐 API 和 UI 可见性，再录 demo；纯渲染逻辑抽到独立 helper 模块以保持测试干净。
- **Decision:** 选择 Option B。先让产品表面和证据承诺对齐，再做手工 walkthrough。
- **Fix:** `SessionResponse` 新增 `next_action`；Study Coach UI 额外读取 `/mastery` 和 `/trace`；新增 `ui/study_coach_view.py` 承载纯格式化逻辑并展示 mastery、next action、ordered tool trace。
- **Verification:** `$env:PYTHONPATH='src'; pytest tests/api/test_sessions.py tests/ui/test_study_coach_rendering.py tests/ui/test_agent_client.py -v`
- **Result:** Study Coach 界面和 session contract 已能承载手工证据路径。
- **Resume impact:** none

### Issue: FastAPI/Starlette Study Coach API 测试存在第三方弃用 warning

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `tests/api/test_sessions.py`
- **Symptom:** `pytest tests/api tests/ui -q -W default` 输出 `StarletteDeprecationWarning`，影响 Draft PR review cleanliness。
- **Root cause:** API 合同测试依赖 `fastapi.testclient.TestClient`，其底层 `starlette.testclient` + `httpx` 组合已被上游标记为弃用。
- **Options considered:**
  - Option A: 在 evidence 文档中接受 warning，并说明它来自第三方。
  - Option B: 改用 `httpx` ASGI transport，保留同样的 API contract 覆盖，同时清掉 warning。
- **Decision:** 选择 Option B，优先清理可避免的 review 噪音。
- **Fix:** `tests/api/test_sessions.py` 改成基于 `httpx.AsyncClient` + `httpx.ASGITransport` 的异步合同测试。
- **Verification:** `$env:PYTHONPATH='src'; pytest tests/api/test_sessions.py -q -W default`
- **Result:** 测试通过，warning 消失。
- **Resume impact:** none

### Issue: 手工 Study Coach demo 初次运行时检索链无法形成 happy path

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `conda` environment `final-agent`, `src/final_agent/api/app.py`
- **Symptom:** 初次用 `AgentService` 手工录制 evidence 时，`search_course_material` 先后报缺少 runtime 依赖和 `BM25 index not loaded. Call load_index() first.`，导致 trace 中检索步骤不是成功状态。
- **Root cause:** 当前机器未在专用环境中安装项目依赖；补齐依赖后又发现 Streamlit 会预热知识层缓存，但 FastAPI `create_app()` 没有对应的 BM25 warmup。
- **Options considered:**
  - Option A: 直接把失败 trace 写进 evidence 文档，并把它解释成环境限制。
  - Option B: 按 README 的标准安装路径，在 `conda` 环境中补齐依赖，并修复 FastAPI 启动时的知识层预热。
- **Decision:** 选择 Option B，优先让手工证据路径变成真实 happy path。
- **Fix:** 在 `conda` 环境 `final-agent` 中执行 `conda run -n final-agent python -m pip install -e ".[dev]"`；新增 FastAPI knowledge warmup，在 `create_app()` 时加载 Chroma chunks 并恢复 BM25 缓存。
- **Verification:** `conda run --no-capture-output -n final-agent python <api demo script>`；观察 `search_course_material` trace `ok=True` 且 `next_action=practice_variant`。
- **Result:** 本地 `FastAPI -> workflow -> SQLite` 证据路径跑通。安装过程中 `pip` 报出一条现有环境里的 `aiobotocore`/`botocore` 兼容性 warning，但未阻断 `final-agent` 环境安装。
- **Resume impact:** none

### Issue: 安装完整依赖后 API 测试出现新的 `jieba/pkg_resources` 第三方 warning

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `src/final_agent/retrieval/query_expander.py`, `src/final_agent/knowledge/bm25_index.py`, `tests/retrieval/test_query_expander.py`
- **Symptom:** 在 `conda` 环境里跑 API 合同测试时，Starlette warning 已消失，但新的 warnings summary 显示 `jieba._compat` 发出的 `pkg_resources is deprecated as an API`。
- **Root cause:** `query_expander` 和 BM25 tokenization 在导入/首次调用 `jieba` 时会触发上游包的兼容层 warning。
- **Options considered:**
  - Option A: 在 pytest 配置里全局忽略这个 warning。
  - Option B: 保持测试和运行日志安静，在自家 `jieba` 接入点做定点惰性导入和 warning 抑制。
- **Decision:** 选择 Option B，避免把 review cleanliness 建立在全局忽略规则上。
- **Fix:** `query_expander` 改为运行时惰性导入 `jieba`；`query_expander` 和 `bm25_index` 的 `jieba` 接入点都加入定点 warning 抑制；新增回归测试确保导入和调用路径不再冒出该 warning。
- **Verification:** `conda run -n final-agent python -m pytest tests/retrieval/test_query_expander.py -v`；`conda run -n final-agent python -m pytest tests/api/test_sessions.py -q -W default`
- **Result:** API 合同测试和 query expander 回归测试通过，相关 warnings summary 清空。
- **Resume impact:** none

### Issue: Study Coach final evidence package 收口

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `README.md`, `DESIGN.md`, `docs/final-agent-study-coach-demo-evidence.md`
- **Symptom:** 仓库已有 bounded workflow 和离线评测，但缺少一条可复现的手工 walkthrough、示例 mastery 结果、ordered trace 与可直接讲解的 demo script。
- **Root cause:** 之前的工作优先把实现和 deterministic evaluation 做完，文档层的演示证据没有单独整理。
- **Options considered:**
  - Option A: 只在 README 里追加长段说明。
  - Option B: README 保持高层摘要，详细 walkthrough 单独放到 `docs/final-agent-study-coach-demo-evidence.md`。
- **Decision:** 选择 Option B，形成 README + 独立 evidence note 的双层发布结构。
- **Fix:** 新增独立 demo evidence 文档，记录 `POST /sessions`、`POST /messages`、`GET /mastery`、`GET /trace` 的关键输出、happy path 步骤、限制说明和 90 秒 demo script；同步更新 README 和 DESIGN。
- **Verification:** 人工核对文档中的 payload、trace 顺序、mastery 分数、`practice_variant` 与实际 API demo 输出一致。
- **Result:** Draft PR 具备清晰、可复现、口径克制的手工证据路径。
- **Resume impact:** can mention bounded workflow evidence, still no live LLM quality claim

### Issue: Quiz generator adapter 需要可注入实现而不是隐藏全局状态

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `src/final_agent/agent/quiz_generators.py`, `src/final_agent/agent/graph.py`, `src/final_agent/api/app.py`
- **Symptom:** `generate_quiz` 之前把 deterministic 规则写死在 tool 里，后续要接 LLM 版本时，没有明确的 adapter 边界，也没有启动时组装点。
- **Root cause:** 第一版 Study Coach 先追求最小可跑通 workflow，把 quiz 生成直接内联进 tool，导致实现选择只能靠修改函数体本身。
- **Options considered:**
  - Option A: 在 `tools.py` 或 `graph.py` 里读全局默认实现，调用方无感知，接线最省事。
  - Option B: 新增 quiz generator adapter，并在 app/service 注入层显式组装，再一路传到 workflow。
- **Decision:** 选择 Option B。默认实现暂时仍是 deterministic，但边界已经固定为可注入 adapter。
- **Fix:** 新增 `DeterministicQuizGenerator` 和 `LlmQuizGenerator`；`generate_quiz` 改为委托注入对象；`run_study_turn` 和 `AgentService` 接收 `quiz_generator`；`create_app()` 在启动时完成默认组装。
- **Fallback policy:** LLM 调用、JSON 解析或 `QuizQuestion` 校验失败时，不让 workflow 失败，而是在 adapter 内部回退到 deterministic；graph trace 通过 `impl=...` 和 `error/fallback_reason` 暴露该事实。
- **Why not global default state:** 这样部署后要切换实现时，只需要在启动装配层替换 generator，不用改 workflow 代码，也更容易做测试注入。
- **Verification:** `conda run -n final-agent python -m pytest tests/agent/test_quiz_generators.py tests/agent/test_tools.py tests/agent/test_graph.py tests/api/test_sessions.py -v`
- **Result:** adapter 边界、fallback 语义和 app-level assembly 都有回归测试保护。
- **Resume impact:** can mention explicit adapter injection and deterministic fallback policy

### Issue: Grader adapter 需要和 quiz adapter 一样在启动时显式组装

- **Date:** 2026-06-21
- **Status:** resolved
- **Where:** `src/final_agent/agent/graders.py`, `src/final_agent/agent/graph.py`, `src/final_agent/api/app.py`
- **Symptom:** grading 逻辑原先只是一段固定规则，后续如果接 LLM 评分、保留 deterministic fallback，workflow 本身没有明确装配边界，也不方便在测试里替换实现。
- **Root cause:** 第一版 Study Coach 为了先跑通闭环，把评分实现直接耦合在 workflow/tool 路径里，没有像 quiz generation 那样抽出 adapter seam。
- **Options considered:**
  - Option A: 继续在 tool 或 graph 内部隐式选择默认 grader，实现简单，但部署切换和测试注入都要改 workflow 代码。
  - Option B: 新增 grader adapter，默认实现放到 service / app 注入层启动时组装，再一路透传到 workflow。
- **Decision:** 选择 Option B。部署默认值使用 `LlmGrader(fallback=DeterministicGrader())`，把 fallback 留在 adapter 内部，workflow 只依赖统一评分接口。
- **Fix:** 新增 `DeterministicGrader` 与 `LlmGrader`；`run_study_turn` 接收注入 grader 并把 `impl=...` / fallback reason 写进 trace；`AgentService` 与 `create_app()` 在启动时默认组装 LLM grader；保留 `materials` 参数以便后续把 grounded grading 接入同一 adapter 接口，而不需要再次改调用栈。
- **Verification:** `conda run -n final-agent python -m pytest tests/agent/test_graders.py tests/agent/test_tools.py tests/agent/test_graph.py tests/api/test_sessions.py -v`
- **Result:** grading seam、默认部署策略和 trace observability 都有测试覆盖，后续真实部署只需要在启动装配层替换 grader 实现。
- **Resume impact:** can mention startup-time assembly and reserved `materials` hook for grounded grading

## Phase 11 — Knowledgebase Scaling / Course-Scoped Sparse Index

### Issue: 知识库变大后，BM25 全局快照和启动预热会拖慢 UI/API 启动与检索

- **Date:** 2026-06-26
- **Status:** resolved
- **Where:** `src/final_agent/knowledge/metadata.py`, `src/final_agent/knowledge/bm25_index.py`, `src/final_agent/knowledge/builder.py`, `src/final_agent/retrieval/hybrid_searcher.py`, `src/final_agent/ui/app.py`, `src/final_agent/api/app.py`
- **Symptom:** 知识库增大后，BM25 仍按“全库一个缓存”处理；UI 和 FastAPI 启动时还会阻塞式预热知识库，导致初始化慢，检索成本随全库增长而不是随选中课程增长。
- **Root cause:** 稀疏检索层把 BM25 当作一个全局缓存，没有课程级快照路由；导入/删除时会影响整库；检索前也没有真正按课程惰性装载。
- **Options considered:**
  - Option A: 继续保留全局 BM25 快照，只优化 warmup 时机。
  - Option B: 把 BM25 拆成课程级快照，metadata 记录 snapshot path，导入/删除只重建受影响课程，检索时按课程懒加载。
- **Decision:** 选择 Option B。保留 Chroma 作为 dense store，把 BM25 改造成 course-scoped sparse partitions，并移除 UI/API 启动时的阻塞预热。
- **Fix:**
  - `metadata.py`: `register_document()` 新增 `bm25_snapshot_path`，新增 `list_course_index_info()` 聚合课程级 chunk/document/snapshot 信息。
  - `bm25_index.py`: 新增 `course_index_path()`、`build_index_for_course()`、`ensure_course_loaded()`；删除文档时优先使用 metadata 记录的 snapshot path 回写。
  - `builder.py`: 导入时只重建当前课程的 BM25 分区，并把 snapshot path 写回 metadata。
  - `hybrid_searcher.py`: sparse 检索改为按课程逐个懒加载；支持单课程、多课程、无 scope 三种路径；不再每次 `get_all_chunks()` 全库扫描。
  - `api/app.py`: 删除 `create_app()` 里的 eager BM25 warmup。
  - `ui/app.py`: 删除启动时全量知识库 warmup，改为展示 readiness 状态；新增 `ui/knowledge_status.py` 负责纯文本状态格式化。
- **Tests added:**
  - `tests/knowledge/test_metadata.py`
  - `tests/knowledge/test_bm25_index.py`
  - `tests/retrieval/test_hybrid_searcher.py`
  - `tests/ui/test_knowledge_status.py`
  - `tests/api/test_sessions.py` 同步改成断言 app 启动不再预热知识库
- **Verification:**
  - `conda run -n final-agent python -m pytest tests/knowledge/test_metadata.py tests/knowledge/test_bm25_index.py tests/retrieval/test_hybrid_searcher.py tests/retrieval/test_pipeline.py tests/api/test_sessions.py tests/ui/test_knowledge_status.py tests/ui/test_study_coach_rendering.py -v`
  - `conda run -n final-agent python -m ruff check src tests`
  - `conda run -n final-agent python -m pytest --cov=final_agent --cov-report=term-missing`
- **Result:** 关键回归通过；当前全量 `70 passed`。知识库启动路径从“阻塞预热”改为“按课程惰性装载”，更适合后续知识库继续增长。
- **Resume impact:** can mention course-scoped sparse indexing, lazy retrieval loading, and startup readiness instead of eager warmup

## Phase 12 — Apple 风格 Streamlit UI 重构计划

### Issue: 前端需要从功能原型界面升级为 Apple-like 学习工作台，同时确认是否牵动后端

- **Date:** 2026-06-29
- **Status:** planned
- **Where:** `src/final_agent/ui/app.py`, `src/final_agent/ui/study_coach_view.py`, `src/final_agent/ui/agent_client.py`, `src/final_agent/api/app.py`, `src/final_agent/api/schemas.py`
- **Symptom:** 当前 Streamlit UI 已覆盖上传、问答、总结、课程切换、幻觉校验和 Study Coach，但信息层级偏功能堆叠，视觉还停留在原型阶段。
- **Root cause:** 之前的开发优先保证 RAG、知识库扩容、Study Coach workflow 和证据路径可运行；产品交互层尚未单独做视觉系统和信息架构整理。
- **Options considered:**
  - Option A: 迁移到独立 React/Next 前端，更容易做精细 Apple 风格交互，但需要把现有 Streamlit 直调 Python 模块的路径 API 化，架构改动大。
  - Option B: 保留 Streamlit，在现有架构内做 Apple-like redesign，最快落地，并最大限度复用现有 RAG 和 Study Coach 调用路径。
- **Decision:** 选择 Option B。用户明确选择保留 Streamlit，而不是迁移 React/Next 独立前端。
- **Design definition:** Apple 风格在本项目中定义为工具型产品 UI：浅色背景、系统字体、柔和分区、清晰状态卡片、克制蓝色强调、低噪音层级；不做 Apple 官网式营销 hero。
- **Planned UI change:** 重组侧边栏与主工作区，让学习会话、检索范围、知识库、模型/API 配置、引用、幻觉校验和 Study Coach 状态更容易扫读。
- **Backend impact check:** grill 检查结论是前端表现层改变不会迫使 FastAPI、Pydantic schema、SQLite memory 或 agent graph 改动。
- **Why backend can stay unchanged:** Study Coach API 已能提供 session、mastery、trace；本次前端只重新组织这些字段的展示，不新增字段。
- **Optional backend follow-up:** 后续可考虑 `/health` endpoint、可配置 `AgentApiClient` base URL、错误状态细分，但它们不是本次 UI 重构的前置条件。
- **Verification plan:** 文档层先记录架构边界和决策；实现 UI 时再跑 `tests/ui`、`tests/api` 与手动 Streamlit 验收。

---

## Phase 12 — Multi-Agent Study Coach Architecture

### Decision: 多 Agent 范围限定为 Multi-Agent Study Coach

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** 下一阶段的“多 agent 协作”定义为 **Multi-Agent Study Coach**：多个固定角色 agent 围绕学习闭环协作，而不是通用自治 agent 平台。
- **Decision reason:** 当前项目最强的定位是本地优先、课程知识库驱动、可测试、可解释的学习系统。直接做通用自治平台会削弱 bounded workflow 的可信度，也会让测试、UI trace 和项目汇报变得发散。
- **Rejected alternative:** 通用 agent swarm / open-ended autonomous agent platform。它更酷但边界不清，容易引入无限规划、不可控 tool calling、难以复现的结果。
- **Architecture implication:** 保留现有 `Study Coach` 学习闭环作为主线，只把单一 workflow 拆成固定职责 agent：Supervisor、Retrieval、Quiz、Grader、Coach、Critic。
- **Resume/interview framing:** 不是“我做了一个全自治 agent”，而是“我把 RAG 学习系统升级为 bounded multi-agent learning workflow，并保留 typed tools、trace、memory 和 deterministic regression tests。”

### Decision: v1 采用固定顺序协作

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Multi-Agent Study Coach v1 采用 **Fixed Sequential Collaboration**，即固定顺序执行：Supervisor -> Retrieval -> Quiz -> wait_for_answer -> Grader -> Coach -> Critic -> final response。
- **Decision reason:** 现有 `run_study_turn` 已经是顺序 bounded workflow，固定顺序迁移成本最低，最容易保持测试稳定，也最容易在 Streamlit 中展示“哪个 agent 做了什么”。
- **Rejected alternative:** 第一版就做并行 agent 或 supervisor 动态自由调度。并行和动态调度会让 tool-call limit、失败恢复、trace 顺序、UI timeline 和离线评测复杂度显著上升。
- **Architecture implication:** 第一阶段先重构 agent 边界和 tool call trace，不改变用户可见学习闭环；并行检索、并行 critique、动态调度作为后续演进点。
- **Testing implication:** 每个 agent 的输入、输出、allowed tools 和 trace entry 都可以独立断言；端到端测试仍保持 deterministic fallback。

### Decision: v1 固定为 6 个 Agent Role

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Multi-Agent Study Coach v1 固定为 6 个角色：Supervisor Agent、Retrieval Agent、Quiz Agent、Grader Agent、Coach Agent、Critic Agent。
- **Decision reason:** 这 6 个角色刚好覆盖现有学习闭环的关键责任边界：规划、检索证据、出题、批改、更新掌握度/选择下一步、最终一致性检查。它们能把当前单 workflow 拆成清晰的可解释协作链，而不改变用户可见主流程。
- **Rejected alternative:** 第一版加入 Planner Agent、Memory Agent、Reflection Agent、Research Agent 等更多角色。现有系统已经有 plan、SQLite memory、tool trace 和 retrieval/generation 层；过度拆分会变成“为了多 agent 而多 agent”，增加 UI 和测试噪音。
- **Architecture implication:** `agent/` 层后续应新增 role-level abstraction，但 memory、tool registry、retrieval 和 grading adapter 不需要被重新命名成 agent；它们仍是被角色调用的能力。
- **Testing implication:** 每个角色都应有 allowed tools、输入/输出 schema 和 trace entry；第一版测试重点是角色边界和工具调用顺序，而不是模型自主规划质量。
- **Resume impact:** can describe a bounded multi-agent learning workflow with six fixed roles, typed tool calls, persistent memory, and explainable traces.

### Decision: Specialist Agent 使用严格 Tool Boundary

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Supervisor Agent 不直接调用业务 tools，只负责编排；每个 specialist agent 只能调用自己的 allowed tools。
- **Allowed tools:**
  - Supervisor Agent: none
  - Retrieval Agent: `search_course_material`, `summarize_course`
  - Quiz Agent: `generate_quiz`
  - Grader Agent: `grade_answer`
  - Coach Agent: `get_learning_profile`, `update_mastery`
  - Critic Agent: `verify_evidence`, `verify_grade_consistency`
- **Decision reason:** 如果 Supervisor 能直接 search/generate/grade，它会变成万能 agent，其他角色只剩命名装饰，多 agent 边界会失真。严格 tool boundary 能让职责、trace、测试和 UI timeline 都更清楚。
- **Rejected alternative:** 所有 agent 共用全局工具池，由 prompt 自觉遵守职责。这个方案实现快，但很难证明角色边界，也容易出现“看起来多 agent，实际还是一个万能 agent”的问题。
- **Architecture implication:** 后续 tool registry 需要支持 role-level allowlist；`verify_evidence` 和 `verify_grade_consistency` 是 Critic Agent 需要补的新 typed tools。
- **Testing implication:** 测试必须覆盖“角色不能调用未授权 tool”的失败路径，并验证 trace 能记录 agent role、tool name、input summary、ok/error 和 elapsed time。

### Decision: v1 Tool Calling 采用 Internal Typed Tool Calling

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Multi-Agent Study Coach v1 的 tool calling 采用项目内部协议：agent 产出 `ToolCall(name, arguments)`，`ToolRegistry` 校验 role permission 和 Pydantic arguments，执行 Python tool 后返回 `ToolResult`。
- **Decision reason:** 当前项目已有 Python typed tools 和 Pydantic schema，内部协议最容易保持离线可测、可解释和跨模型稳定。这样 tool calling 的核心契约属于项目本身，而不是某个 LLM provider 的 function calling JSON 格式。
- **Rejected alternative:** 第一版直接依赖 DeepSeek/OpenAI native function calling，让模型按 provider 协议决定工具调用。这个方案更接近真实 agent demo，但会让测试依赖模型行为和 provider 格式，也会增加解析/错误恢复复杂度。
- **Architecture implication:** Provider-native function calling 后续作为 adapter 接入：把模型返回的 tool call 转换成内部 `ToolCall`，再交给同一个 registry 执行。
- **Testing implication:** v1 测试重点是内部 `ToolCall` schema、role allowlist、argument validation、tool execution result 和 trace persistence；不把 live model tool selection 作为稳定回归条件。

### Decision: Trace 升级为 Agent Tool Trace，但只保存摘要

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** 后续 trace 从 tool-only trace 升级为 **Agent Tool Trace**，记录 `sequence_no`, `agent_role`, `tool_name`, `input_summary`, `output_summary`, `ok`, `elapsed_ms`, `error`, `fallback_reason`。
- **Decision reason:** 多 agent 协作需要回答“哪个 agent 调了哪个 tool、结果如何、是否 fallback”，但 trace 的目的不是保存完整 prompt/chunk/raw model response。摘要级 trace 更适合 UI timeline、debug、测试和面试讲解。
- **Rejected alternative:** 把完整 prompt、完整 retrieved chunks、完整 learner answer、raw LLM response 全部写入 SQLite trace。这样短期调试方便，但会让数据库膨胀，增加隐私风险，也让 UI 和测试被噪音淹没。
- **Architecture implication:** 需要扩展现有 `ToolTraceEntry` / SQLite `tool_traces` schema；完整证据仍通过 citation registry、chunk store 或按需查询展示，不塞进 trace。
- **Testing implication:** 测试应断言 trace 的 role、tool、摘要、fallback_reason 和顺序，而不是依赖完整自然语言 prompt。

### Decision: Critic Agent v1 只提示不阻断

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Critic Agent v1 执行 `verify_evidence` 和 `verify_grade_consistency` 后只产出 non-blocking flags/warnings，并附加到 response 与 trace；它不阻断主学习回合。
- **Decision reason:** 第一版 Critic 的核心价值是增加可解释性和可观察性，而不是改变控制流。阻断式 Critic 会引入重试、回滚、重新生成 quiz/regrade、用户等待时间和更复杂的失败恢复。
- **Rejected alternative:** Critic 一旦发现问题就停止回答、强制 regenerate quiz 或 regrade。这个方案更“智能”，但会让 v1 的 bounded workflow 难测且容易出现循环。
- **Architecture implication:** `CriticWarning` 应作为响应和 trace 的附加信息；后续可以根据真实验收数据再决定哪些 warning 升级为 hard gate。
- **Testing implication:** 测试应验证 warning 被记录和展示，但即使 Critic 发现 warning，session 仍能进入正常 completed / waiting state。

### Decision: Multi-Agent v1 扩展现有 AgentState

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Multi-Agent Study Coach v1 扩展现有 `AgentState`，不创建一套平行的新 session state。
- **Decision reason:** 现有 API、UI、SQLite memory、evaluation harness 和测试都围绕 `AgentState` / session contract 建立。扩展现有 state 可以保留兼容性，并允许旧 Study Coach 路径逐步迁移到 multi-agent trace。
- **State additions:** `agent_plan`, `agent_trace`, `critic_warnings`, `current_agent_role`。
- **State retained:** `session_id`, `learning_goal`, `course_ids`, `plan`, `quiz`, `learner_answer`, `grade`, `next_action`, `status`, `tool_trace`, `tool_call_count`。
- **Rejected alternative:** 新建一套 `MultiAgentState` / 新 session table / 新 API contract。这个方案边界干净，但会造成重复状态、迁移成本高，也容易让 Streamlit 和 FastAPI 出现两套 Study Coach 行为。
- **Architecture implication:** 数据库 `sessions.state_json` 可以自然承载扩展字段；如果需要结构化查询，再增量迁移表结构，而不是预先拆库。
- **Testing implication:** 旧 session API contract 测试应继续通过；新增测试只验证扩展字段存在和 multi-agent trace 行为。

### Decision: 复用现有 Study Coach Session API

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Multi-Agent Study Coach 继续复用现有 `/sessions` API contract，不新建 `/multi-agent/*` namespace。
- **Decision reason:** 对用户和 Streamlit UI 来说，这仍然是 Study Coach 模式，只是后端从单 workflow 演进为 fixed-role multi-agent workflow。保持 API 稳定可以避免 UI/client/evaluation 分叉。
- **Retained endpoints:** `POST /sessions`, `POST /sessions/{id}/messages`, `GET /sessions/{id}`, `GET /sessions/{id}/mastery`, `GET /sessions/{id}/trace`。
- **Possible additive endpoint:** 后续如果 UI 需要更细 timeline，可增加 `GET /sessions/{id}/agent-trace`，但第一版不引入独立 multi-agent namespace。
- **Rejected alternative:** 新增 `/multi-agent/sessions` 和一套 parallel API。这个方案更显式，但会让旧 Study Coach 和新 Multi-Agent Study Coach 在产品上分裂。
- **Architecture implication:** `SessionResponse` 可以增量暴露 `agent_plan`, `critic_warnings` 等字段；老客户端仍能读取已有字段。
- **Testing implication:** 现有 API contract tests 必须继续通过；新增字段测试应保持 backward-compatible。

### Decision: 第一阶段只做 Multi-Agent Execution Skeleton

- **Date:** 2026-07-08
- **Status:** accepted
- **Decision:** Multi-Agent Study Coach 第一阶段只实现 execution skeleton：`AgentRole`、`ToolCall` / `ToolSpec` / `ToolRegistry`、role-level allowed tools、固定顺序 orchestrator、`AgentToolTrace`、`CriticWarning`、API response 扩展、UI timeline 和 deterministic tests。
- **Decision reason:** 这一阶段的目标是先把多 agent 边界、tool calling 契约和可观察性立起来，而不是马上追求模型自主规划。这样能最快获得可测试、可展示、可逐步替换 adapter 的架构基础。
- **Explicitly out of scope for stage 1:** LLM supervisor autonomous planning、provider-native function calling、parallel execution、retry/regenerate control loop、新 API namespace。
- **Architecture implication:** 第一阶段不改变用户学习闭环，只改变内部执行结构和 trace 可视化；旧 deterministic fallback 仍是回归测试基线。
- **Testing implication:** 回归测试应验证 role sequence、allowed tools、tool argument validation、trace persistence、critic warnings 和 API backward compatibility。

### Stage 2 Outlook: LLM-assisted Agent Decisions

- **Target:** 在第一阶段 skeleton 稳定后，引入有限的 LLM-assisted decisions，但仍保持 bounded workflow。
- **Candidate upgrades:**
  - Supervisor Agent 可以用 LLM 生成解释性 plan rationale，但仍只能选择预定义 role sequence 的变体。
  - Retrieval Agent 可以用 LLM 做 query expansion / evidence selection rationale，但检索仍通过 typed tools。
  - Quiz Agent 和 Grader Agent 使用 live adapters，并把 fallback reason 写入 AgentToolTrace。
  - Critic Agent 可以从规则校验升级为 LLM-assisted consistency review，但 warning 仍默认 non-blocking。
  - Provider-native function calling 作为 adapter，把 DeepSeek/OpenAI tool call JSON 转换为内部 `ToolCall`。
  - 可探索有限并行：Retrieval Agent 的 multi-query retrieval 或 Critic Agent 的 evidence/grade checks 并行执行。
- **Guardrails:** Stage 2 仍不做 open-ended autonomous agent swarm；仍保留 role allowlist、tool-call limit、typed schema、trace persistence 和 deterministic fallback tests。
- **Success signal:** live model 能提升 quiz/grading/critic 质量，但离线 deterministic suite 仍可复现通过，UI 能解释每个 role 和 tool call。

### Stage 1 Acceptance Criteria

- **Date:** 2026-07-08
- **Status:** accepted
- **Acceptance criteria:**
  1. 同一个 Study Coach session 能跑完整学习回合。
  2. trace 中能看到 6 个 agent role 的固定顺序：Supervisor、Retrieval、Quiz、Grader、Coach、Critic。
  3. 每个 role 的 tool call 都经过 allowed-tools 校验。
  4. 未授权 tool call 会失败，并作为错误写入 Agent Tool Trace。
  5. Critic warning 能显示在 API/UI 中，但不阻断 session completed / waiting state。
  6. 旧 Study Coach API contract tests 继续通过。
  7. deterministic evaluation 继续离线可跑。
- **Decision reason:** 这些标准能证明多 agent 架构不是只有命名变化，而是具备角色边界、工具权限、可观察 trace、非阻断 critic 和 backward compatibility。
- **Implementation implication:** Stage 1 实现计划必须优先覆盖 role model、tool registry、orchestrator、trace persistence、critic warnings、API/UI 扩展和 deterministic tests。

### Issue: PDF 导入速度需要优先于最高图片清晰度

- **Date:** 2026-06-29
- **Status:** resolved
- **Where:** `config.yaml`, `src/final_agent/settings.py`
- **Symptom:** 导入新 PDF 文档仍然偏慢，用户希望继续压缩导入等待时间。
- **Root cause:** Doubao PDF 解析链路会先用 `pypdfium2` 把每页渲染为 PNG，再 base64 上传给 VLM；`page_dpi=200` 会增加本地渲染时间、图片体积和 API 请求负载。
- **Options considered:**
  - Option A: 保持 200 DPI，优先解析清晰度和复杂公式/小字识别。
  - Option B: 将默认 DPI 降到 150，优先导入速度和请求体积，接受少量清晰度下降。
- **Decision:** 选择 Option B。默认 `page_dpi` 从 `200` 调低到 `150`，更适合日常课件导入。
- **Fix:** `config.yaml` 与 `VisionSettings.page_dpi` 默认值同步改为 `150`，避免缺少配置文件时回退到 200。
- **Tradeoff:** 150 DPI 对普通文字课件通常足够；如果遇到小字号扫描件、复杂公式或低清晰度图片，可临时把 `config.yaml` 改回 200。
- **Verification:** 配置层改动，不改变 API/schema；后续导入 PDF 时 UI 仍会展示页数、批次数和 Doubao 并发信息。
- **Resume impact:** can mention PDF import now defaults to 150 DPI for faster rendering and smaller VLM payloads

## Phase 13 — Course-Scoped Knowledge Productization / UI Polish

### Issue: 所有课程共用一个知识库会让检索范围和维护边界变得模糊

- **Date:** 2026-07-07
- **Status:** resolved
- **Where:** `src/final_agent/knowledge/vector_store.py`, `src/final_agent/knowledge/metadata.py`, `src/final_agent/knowledge/maintenance.py`, `src/final_agent/ui/app.py`
- **Symptom:** 用户明确指出“所有的课程都用一个知识库会不会太冗杂”，希望“一门课程只有一个专门对应的知识库”。
- **Root cause:** Phase 8 的课程分组仍然建立在单一 dense collection + metadata 过滤上；虽然能减少跨课程污染，但物理维护边界仍然不清晰，后续迁移、修复、删除和扩容都容易牵动全局。
- **Options considered:**
  - Option A: 继续使用单一 Chroma collection，只依赖 `course_id` where 过滤，改动小但课程隔离不彻底。
  - Option B: dense 和 sparse 都升级为课程级分区：Chroma 使用课程级 collection，BM25 使用课程级 snapshot，metadata 作为课程目录。
- **Decision:** 选择 Option B。课程是 final-agent 当前最重要的知识库边界，dense/sparse/metadata/UI 都应该围绕课程组织。
- **Fix:** 新增课程级 Chroma collection 命名与查询路由；保留旧全局 collection 作为兼容来源；新增 `rebuild_course_knowledge()` 聚合迁移和 sparse 重建；UI 提供当前课程知识库维护入口。
- **Verification:** `pytest tests/knowledge tests/retrieval tests/api/test_sessions.py tests/ui -q`；`python -m ruff check src/final_agent/knowledge src/final_agent/retrieval src/final_agent/ui tests/knowledge tests/retrieval tests/ui`
- **Result:** 课程级知识库从“逻辑过滤”推进到“物理分区 + 可维护入口”。
- **Resume impact:** can mention one course maps to one dedicated dense collection and one sparse snapshot

### Issue: legacy Chroma 迁移时报 numpy array truth value ambiguous

- **Date:** 2026-07-07
- **Status:** resolved
- **Where:** `src/final_agent/knowledge/vector_store.py`
- **Symptom:** UI 执行迁移时报错：`The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()`。
- **Root cause:** Chroma 返回的 embedding 可能是 numpy array；迁移逻辑用普通 truthiness 判断数组是否存在，触发 numpy 的 ambiguous truth value 错误。
- **Options considered:**
  - Option A: 跳过旧 embedding，重新计算 embedding，逻辑简单但成本高且依赖模型运行环境。
  - Option B: 显式判断 `is None`，并在写入前把 array 转为 list，保留原有 embedding。
- **Decision:** 选择 Option B。迁移应该尽量是数据搬运，不应强制重新跑 embedding。
- **Fix:** 迁移路径改用显式空值判断和 `.tolist()` 标准化，避免对 numpy array 做布尔判断。
- **Verification:** 增加迁移回归测试；运行知识库和检索相关测试。
- **Result:** 旧全局 collection 可以安全迁移到课程级 collection。
- **Resume impact:** can mention migration keeps existing embeddings and fixes numpy truthiness bug

### Issue: 课程选择只有默认课程和全部课程，不能创建新课程

- **Date:** 2026-07-07
- **Status:** resolved
- **Where:** `src/final_agent/knowledge/metadata.py`, `src/final_agent/ui/app.py`, `tests/knowledge/test_metadata.py`
- **Symptom:** 课程选择只能来自已有文档 metadata；在上传新课程资料前，用户不能先创建一个命名明确的课程。
- **Root cause:** `list_courses()` 只从已导入文档反推课程，没有显式课程 registry；空课程在系统里没有存在感。
- **Options considered:**
  - Option A: 上传文档时再输入课程名，不支持预先创建课程。
  - Option B: metadata 支持显式课程 registry，允许创建空课程，且只允许删除没有文档的课程。
- **Decision:** 选择 Option B。课程是用户组织资料的入口，而不只是文档导入后的派生属性。
- **Fix:** 新增 `create_course()` 和 `delete_empty_course()`；`list_courses()` 合并显式课程和文档派生课程；UI 增加“新建课程”和“删除当前空课程”。
- **Verification:** `pytest tests/knowledge/test_metadata.py tests/ui/test_workspace.py -q`
- **Result:** 用户可以先建课程，再围绕该课程上传和维护资料。
- **Resume impact:** can mention explicit empty-course lifecycle is supported

### Issue: Apple-like UI 初版顶部暗色模块与整体浅色界面冲突

- **Date:** 2026-07-07
- **Status:** resolved
- **Where:** `src/final_agent/ui/theme.py`, `src/final_agent/ui/app.py`
- **Symptom:** 页面整体走浅色 Apple-like 风格，但顶部突然出现暗色模块，视觉割裂。
- **Root cause:** 初版 header 试图强化品牌感，但 final-agent 是学习工作台，不是营销页；暗色 hero 把注意力从工作区抢走。
- **Options considered:**
  - Option A: 保留暗色 header，调浅或缩小。
  - Option B: 直接移除顶部暗色模块，让浅色工具界面成为第一屏主视觉。
- **Decision:** 选择 Option B。工具型学习产品应优先降低视觉噪音，让问答、课程和知识库状态成为主角。
- **Fix:** 移除突兀暗色 header，保留浅色系统字体、柔和分区和克制蓝色强调。
- **Verification:** 浏览器刷新后确认顶部不再出现暗色模块。
- **Result:** UI 风格从“混合 hero + 工具台”收敛为浅色学习工作台。
- **Resume impact:** can mention no dark hero; Apple-like is applied as quiet productivity UI

### Issue: Evidence 常驻右侧栏挤压中间问答区域

- **Date:** 2026-07-07
- **Status:** resolved
- **Where:** `src/final_agent/ui/app.py`, `src/final_agent/ui/workspace.py`
- **Symptom:** 右侧 Evidence 模块常驻后，主问答区域变窄，影响核心阅读和对话体验。
- **Root cause:** Evidence 是重要的可解释性辅助信息，但不是每一轮都需要常驻占据布局宽度。
- **Options considered:**
  - Option A: 保持三栏布局，缩小 Evidence 宽度。
  - Option B: Evidence 默认隐藏，用按需 popover 打开。
- **Decision:** 选择 Option B。主问答区是核心工作面，证据区应可达但不抢空间。
- **Fix:** Evidence 改为 `st.popover`；新增 `evidence_popover_config()` 作为 UI 文案接口；保留引用、校验和 Coach 支撑信息。
- **Verification:** `pytest tests/ui/test_workspace.py -q`；浏览器确认主问答区域不再被右侧常驻栏挤压。
- **Result:** 问答区域更宽，Evidence 仍可按需打开。
- **Resume impact:** can mention evidence is hidden by default and opened on demand

### Issue: 知识库维护按钮暴露 Chroma / BM25 / dense 等工程词

- **Date:** 2026-07-07
- **Status:** resolved
- **Where:** `src/final_agent/ui/workspace.py`, `src/final_agent/ui/app.py`, `tests/ui/test_workspace.py`
- **Symptom:** 维护区按钮和成功提示直接显示“迁移 Chroma”“dense 迁移”“BM25 chunks”，用户会被底层实现细节打断。
- **Root cause:** 维护功能先从工程操作出发实现，文案没有翻译成学习产品语言。
- **Options considered:**
  - Option A: 保留工程词，方便开发者调试。
  - Option B: 主操作使用用户语言，如“修复当前课程知识库”；高级操作保留为“仅迁移旧向量数据”，底层统计在摘要中转译为旧片段/检索片段。
- **Decision:** 选择 Option B。用户关心课程资料是否可检索、是否修复完成，不需要理解 dense/sparse 的实现。
- **Fix:** 新增 `course_maintenance_copy()`、`format_course_repair_summary()`、`format_course_migration_summary()`；Streamlit 维护区消费这些文案接口。
- **Verification:** `pytest tests/ui/test_workspace.py -q`；`pytest tests/knowledge tests/retrieval tests/api/test_sessions.py tests/ui -q`；`python -m ruff check src/final_agent/knowledge src/final_agent/retrieval src/final_agent/ui tests/knowledge tests/retrieval tests/ui`
- **Result:** 维护区对用户呈现为“修复/整理课程知识库”，底层 Chroma/BM25/dense 不再出现在主要文案里。
- **Resume impact:** can mention maintenance copy is productized and jargon is hidden
