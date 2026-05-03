from typing import List
from rag.base import BaseRetriever
from core.config import settings
import chromadb


class RoutingRetriever(BaseRetriever):
    """查询路由：总结类 / 关键词类 / 语义类，不同问题走不同检索"""

    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._doc_cache: dict = {}

    def index_document(self, document_id: int, file_path: str) -> int:
        chunks = chunk_document(file_path)
        if not chunks:
            return 0

        collection = self.client.get_or_create_collection(f"doc_{document_id}")
        collection.add(
            documents=chunks,
            ids=[f"chunk_{i}" for i in range(len(chunks))],
        )
        self._doc_cache[document_id] = chunks
        return len(chunks)

    def retrieve(self, query: str, document_id: int, top_k: int = 5) -> List[str]:
        question_type = self._classify_question(query)

        if question_type == "summary":
            return self._summary_retrieve(document_id, top_k)
        elif question_type == "keyword":
            return self._keyword_retrieve(query, document_id, top_k)
        else:
            return self._semantic_retrieve(query, document_id, top_k)

    def delete_document(self, document_id: int) -> None:
        try:
            self.client.delete_collection(f"doc_{document_id}")
        except Exception:
            pass
        self._doc_cache.pop(document_id, None)

    def _classify_question(self, query: str) -> str:
        summary_keywords = ["总结", "摘要", "概述", "讲了什么", "主要内容", "整体", "概览"]
        keyword_keywords = ["第几章", "第几页", "数据", "数字", "具体", "精确", "多少"]

        for kw in summary_keywords:
            if kw in query:
                return "summary"
        for kw in keyword_keywords:
            if kw in query:
                return "keyword"
        return "semantic"

    def _summary_retrieve(self, document_id: int, top_k: int) -> List[str]:
        chunks = self._doc_cache.get(document_id, [])
        if not chunks:
            try:
                collection = self.client.get_collection(f"doc_{document_id}")
                results = collection.get(limit=top_k)
                return results["documents"] if results["documents"] else []
            except Exception:
                return []
        return chunks[:top_k]

    def _keyword_retrieve(self, query: str, document_id: int, top_k: int) -> List[str]:
        chunks = self._doc_cache.get(document_id, [])
        if not chunks:
            try:
                collection = self.client.get_collection(f"doc_{document_id}")
                results = collection.get()
                chunks = results["documents"] if results["documents"] else []
            except Exception:
                return []

        keywords = list(query)
        scored = []
        for i, chunk in enumerate(chunks):
            score = sum(1 for kw in keywords if kw in chunk)
            scored.append((score, i, chunk))

        scored.sort(key=lambda x: -x[0])
        return [item[2] for item in scored[:top_k]]

    def _semantic_retrieve(self, query: str, document_id: int, top_k: int) -> List[str]:
        try:
            collection = self.client.get_collection(f"doc_{document_id}")
        except Exception:
            return []

        count = collection.count()
        if count == 0:
            return []

        results = collection.query(query_texts=[query], n_results=min(top_k, count))
        if not results.get("documents") or not results["documents"][0]:
            return []
        return results["documents"][0]


from rag.utils.chunker import chunk_document
