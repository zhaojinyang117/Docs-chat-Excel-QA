# AI 文档聊天 & Excel QA 系统

基于 RAG（检索增强生成）和 PandasAI 的智能文档问答系统，支持 PDF、DOCX、TXT 文档聊天和 Excel、CSV 数据分析。

## ✨ 功能特点

### 📝 文档聊天
- 支持 **PDF、DOCX、TXT** 文件
- 全文本索引与分段向量化
- 检索增强生成（RAG）回答
- **返回答案来源**（文件名、页码、原文片段）
- 多轮对话上下文维护

### 📊 Excel 问答
- 支持 **Excel（.xlsx/.xls）、CSV** 文件
- 自动处理**合并单元格**、**多级表头**
- 自然语言数据查询和计算
- 精确数值计算（避免 LLM 幻觉）
- 返回数据定位（Sheet 名、行号）

### 🔐 用户管理
- 简单用户名登录
- 会话隔离

### 📋 日志审计
- 记录所有用户查询
- 记录检索来源和生成回答
- 支持日志导出

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置 API Key

复制配置示例文件：

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

编辑 `.streamlit/secrets.toml`，填入你的 API Key：

```toml
[llm]
api_key = "your-api-key-here"
base_url = "https://api.openai.com/v1"  # 或其他兼容服务
model = "gpt-3.5-turbo"

[embedding]
api_key = "your-api-key-here"
base_url = "https://api.openai.com/v1"
model = "text-embedding-ada-002"
```

**支持的 OpenAI 兼容服务：**
- OpenAI
- 硅基流动 (SiliconFlow)
- DeepSeek
- 智谱 AI
- Groq
- 等其他兼容服务

### 3. 运行应用

```bash
# 使用 uv
uv run streamlit run app.py

# 或直接运行
streamlit run app.py
```

访问 http://localhost:8501

## 📁 项目结构

```
Docs-chat-Excel-QA/
├── app.py                      # Streamlit 主入口
├── config.py                   # 配置管理
├── pyproject.toml              # 依赖配置
├── .streamlit/
│   └── secrets.toml.example    # API Key 配置示例
├── src/
│   ├── llm_factory.py          # LLM/Embedding 初始化
│   ├── engines/
│   │   ├── doc_chat_engine.py  # 文档 RAG 引擎
│   │   └── excel_qa_engine.py  # Excel QA 引擎
│   ├── processors/
│   │   ├── document_processor.py  # 文档处理
│   │   └── excel_processor.py     # Excel 预处理
│   ├── stores/
│   │   └── vector_store.py     # FAISS 向量存储
│   └── utils/
│       ├── logger.py           # 日志审计
│       └── auth.py             # 用户认证
├── data/                       # 向量索引存储
└── logs/                       # 审计日志
```

## 💡 使用示例

### 文档问答

1. 上传一份 PDF 文档（如公司年报）
2. 提问："这份报告的主要结论是什么？"
3. 系统返回答案，并显示来源段落和页码

### Excel 问答

1. 上传一份 Excel 文件（如销售数据）
2. 提问："2024年Q1哪个产品的销售额最高？"
3. 系统返回产品名、数值，以及数据所在的 Sheet 和行号

## ⚙️ 配置说明

### LLM 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `llm.api_key` | API 密钥 | - |
| `llm.base_url` | API 地址 | https://api.openai.com/v1 |
| `llm.model` | 模型名称 | gpt-3.5-turbo |
| `llm.temperature` | 温度参数 | 0.7 |
| `llm.max_tokens` | 最大 token | 2000 |

### RAG 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `rag.chunk_size` | 文本块大小 | 1000 |
| `rag.chunk_overlap` | 重叠大小 | 200 |
| `rag.top_k` | 检索数量 | 4 |

## 🔧 技术栈

- **前端**: Streamlit
- **LLM 编排**: LangChain
- **向量存储**: FAISS
- **文档解析**: PyPDF、python-docx
- **Excel 处理**: openpyxl、pandas
- **Excel 智能分析**: PandasAI

## 📄 许可证

MIT License
