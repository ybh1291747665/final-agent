# final-agent — 期末复习 Agent

基于 RAG（检索增强生成）的智能复习助手，支持上传 PDF / Markdown 课件，
通过多模态识别提取知识点，结合 DeepSeek V4 Pro 生成带引用标注、
防幻觉的复习解析、模拟题和错题分析。

## 技术栈

- **PDF 解析**: MinerU (hybrid 引擎)
- **嵌入模型**: BAAI/bge-large-zh-v1.5
- **向量数据库**: Chroma
- **重排序**: BAAI/bge-reranker-v2-m3
- **生成模型**: DeepSeek V4 Pro
- **UI**: Streamlit

## 环境配置

使用 Anaconda 管理虚拟环境：

```bash
conda create -n final-agent python=3.11 -y
conda activate final-agent
pip install -e ".[dev]"
```

复制 `.env.example` 为 `.env`，填入 API Key：

```bash
cp .env.example .env
```

## 使用方式

```bash
# 导入知识库
final-agent ingest <pdf_or_md_path>

# 问答模式
final-agent ask "如何理解导数的定义？"

# 复习模式
final-agent review --chapter 3

# 启动 Web UI
final-agent ui
```

## 项目结构

```
src/final_agent/
├── ingestion/    # PDF 解析、Markdown 导入、分块
├── knowledge/    # 嵌入、向量库、元数据存储、索引
├── retrieval/    # 查询改写、混合检索、重排序、阈值过滤
├── generation/   # Prompt 模板、LLM 客户端、答案生成
├── ui/           # Streamlit 界面
└── main.py       # CLI 入口
```
