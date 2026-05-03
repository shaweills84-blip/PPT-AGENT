# PPT Agent

上传文档，AI 自动生成 PPT。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Vue Router |
| 后端 | FastAPI + SQLAlchemy |
| 数据库 | MySQL 8.0 |
| 向量检索 | ChromaDB + LangChain |
| PPT 生成 | python-pptx |
| LLM | 支持 OpenAI / Anthropic / DeepSeek / 通义千问等多模型切换 |

## 功能

- 文档上传（PDF / Word / TXT），自动解析与向量化
- 多策略 RAG 检索（基础 / 混合 / 父文档 / 路由），支持查询重写与重排序
- Agent 编排：ReAct 工具调用循环，支持自反思与多轮对话
- PPT 生成与下载
- MCP 协议扩展（检索服务 / 搜索服务）

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入数据库密码和 LLM API Key
```

### 2. Docker Compose 一键启动

```bash
docker compose up -d
```

### 3. 访问

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000

### 本地开发

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 项目结构

```
ppt-agent/
├── backend/
│   ├── agent/          # Agent 编排、子代理、对话记忆
│   ├── api/            # FastAPI 路由
│   ├── core/           # 配置、LLM 客户端
│   ├── db/             # 数据库模型与 CRUD
│   ├── mcp/            # MCP 协议服务
│   ├── ppt/            # PPT 生成器
│   └── rag/            # RAG 检索（多策略）
├── frontend/
│   └── src/            # Vue 3 前端
└── docker-compose.yml
```

## License

MIT
