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
