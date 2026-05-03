from typing import List
from rag.base import BaseRetriever
from rag.utils.chunker import chunk_document
from core.config import settings
import chromadb


class HybridRetriever(BaseRetriever):
    """混合检索：向量语义 + 关键词，RRF 融合两路结果"""

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
        vector_results = self._vector_retrieve(query, document_id, top_k * 2)
        bm25_results = self._bm25_retrieve(query, document_id, top_k * 2)
        merged = self._rrf_merge(vector_results, bm25_results, k=60)
        return merged[:top_k]

    def delete_document(self, document_id: int) -> None:
        try:
            self.client.delete_collection(f"doc_{document_id}")
        except Exception:
            pass
        self._doc_cache.pop(document_id, None)

    def _vector_retrieve(self, query: str, document_id: int, top_k: int) -> List[str]:
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

    def _bm25_retrieve(self, query: str, document_id: int, top_k: int) -> List[str]:
        chunks = self._doc_cache.get(document_id, [])
        if not chunks:
            try:
                collection = self.client.get_collection(f"doc_{document_id}")
                results = collection.get()
                chunks = results["documents"] if results["documents"] else []
            except Exception:
                return []

        tokens = list(query)
        scored = []
        for i, chunk in enumerate(chunks):
            score = sum(1 for t in tokens if t in chunk)
            scored.append((score, i, chunk))

        scored.sort(key=lambda x: -x[0])
        return [item[2] for item in scored[:top_k]]

    def _rrf_merge(self, list_a: List[str], list_b: List[str], k: int = 60) -> List[str]:
        scores: dict[str, float] = {}
        doc_map: dict[str, str] = {}

        for rank, doc in enumerate(list_a):
            key = doc[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(list_b):
            key = doc[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

        sorted_keys = sorted(scores.keys(), key=lambda x: -scores[x])
        return [doc_map[key] for key in sorted_keys]
