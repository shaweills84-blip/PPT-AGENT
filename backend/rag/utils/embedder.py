"""
向量化工具
把文字转成向量（一串数字），相似的文字向量也相近

支持两种模式：
  chroma_default  → ChromaDB 内置的 embedding（推荐，无需额外下载模型）
  huggingface     → 本地运行的 HuggingFace 模型（需要下载模型，国内可能超时）
"""
from core.config import settings


def get_embedder():
    """
    返回 embedding 模型实例
    """
    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            openai_api_key=settings.openai_api_key,
        )
    elif settings.embedding_provider == "huggingface":
        import os
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=settings.huggingface_embedding_model,
        )
    else:
        raise ValueError(
            f"未知的 embedding 提供商: {settings.embedding_provider}，"
            f"可选: openai / huggingface"
        )


def get_chroma_embedding_function():
    """
    返回 ChromaDB 原生的 embedding function
    ChromaDB 内置使用 onnxruntime + all-MiniLM-L6-v2，不需要从网上下载
    比 LangChain 的 HuggingFaceEmbeddings 更稳定
    """
    import chromadb.utils.embedding_functions as ef
    return ef.DefaultEmbeddingFunction()
