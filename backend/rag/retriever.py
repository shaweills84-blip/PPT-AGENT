from rag.base import BaseRetriever
from rag.strategies.basic import BasicRetriever
from rag.strategies.parent_doc import ParentDocRetriever
from rag.strategies.routing import RoutingRetriever
from rag.strategies.hybrid import HybridRetriever

STRATEGY_MAP = {
    "basic": BasicRetriever,
    "parent_doc": ParentDocRetriever,
    "routing": RoutingRetriever,
    "hybrid": HybridRetriever,
}


def get_retriever(strategy: str = "basic") -> BaseRetriever:
    cls = STRATEGY_MAP.get(strategy)
    if cls is None:
        raise ValueError(
            f"未知的RAG策略: {strategy}，可选: {list(STRATEGY_MAP.keys())}"
        )
    return cls()


def smart_retrieve(query: str, document_id: int,
                   strategy: str = "basic",
                   top_k: int = 5,
                   enable_rewrite: bool = True,
                   enable_rerank: bool = True) -> list:
    """完整检索链路：改写 → 检索(2倍召回) → 精排 → Top-K"""
    retriever = get_retriever(strategy)

    search_query = query
    if enable_rewrite:
        from rag.query_rewriter import rewrite_query
        rewritten = rewrite_query(query, strategy="llm")
        if rewritten and rewritten != query:
            search_query = rewritten

    recall_k = top_k * 2 if enable_rerank else top_k
    chunks = retriever.retrieve(search_query, document_id, recall_k)

    if not chunks:
        if enable_rewrite and search_query != query:
            chunks = retriever.retrieve(query, document_id, recall_k)
        if not chunks:
            return []

    if enable_rerank and len(chunks) > top_k:
        from rag.reranker import rerank
        chunks = rerank(query, chunks, strategy="llm_rerank", top_k=top_k)

    return chunks[:top_k]
