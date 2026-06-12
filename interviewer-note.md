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
