import os
from pathlib import Path
from pydantic_settings import BaseSettings

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # 数据库
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "ppt_agent"
    db_user: str = "root"
    db_password: str = ""

    # LLM 多模型切换
    llm_provider: str = "openai"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    mimo_api_key: str = ""
    mimo_api_base: str = "https://api.mimov2.example.com/v1"
    deepseek_api_key: str = ""
    qwen_api_key: str = ""

    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-20250514"
    mimo_model: str = "mimo-v2.5"
    deepseek_model: str = "deepseek-chat"
    qwen_model: str = "qwen-plus"

    # Embedding
    embedding_provider: str = "openai"
    openai_embedding_model: str = "text-embedding-3-small"
    huggingface_embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # 路径
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    chroma_dir: str = "./chroma_db"

    # RAG
    default_rag_strategy: str = "basic"
    default_chunk_size: int = 512
    default_chunk_overlap: int = 50
    enable_query_rewriting: bool = True
    enable_reranking: bool = True

    # Agent
    agent_mode: str = "react"
    enable_self_reflection: bool = True
    agent_max_iterations: int = 8

    # MCP
    enable_mcp: bool = True
    mcp_servers: str = "retrieval,search"

    # 搜索
    web_search_provider: str = "tavily"
    web_search_api_key: str = ""

    # 记忆系统
    enable_memory: bool = True
    short_term_ttl: int = 3600
    short_term_max_entries: int = 50

    model_config = {"env_file": str(ENV_FILE)}


settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)
os.makedirs(settings.chroma_dir, exist_ok=True)
