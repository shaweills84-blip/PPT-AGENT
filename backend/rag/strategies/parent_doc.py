from typing import List
from rag.base import BaseRetriever
from rag.utils.chunker import chunk_document
from core.config import settings
import chromadb


class ParentDocRetriever(BaseRetriever):
    """父文档检索：小块定位 + 大块返回，解决小块上下文不足"""

    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)

    def index_document(self, document_id: int, file_path: str) -> int:
        parent_chunks = chunk_document(
            file_path, strategy="recursive",
            chunk_size=512, chunk_overlap=50
        )
        if not parent_chunks:
            return 0

        child_chunks = chunk_document(
            file_path, strategy="recursive",
            chunk_size=128, chunk_overlap=30
        )

        child_to_parent = []
        for child in child_chunks:
            parent_idx = self._find_parent_chunk(child, parent_chunks)
            child_to_parent.append(parent_idx)

        child_col = self.client.get_or_create_collection(f"doc_{document_id}_child")
        child_col.add(
            documents=child_chunks,
            ids=[f"child_{i}" for i in range(len(child_chunks))],
            metadatas=[{"parent_idx": str(idx)} for idx in child_to_parent],
        )

        parent_col = self.client.get_or_create_collection(f"doc_{document_id}_parent")
        parent_col.add(
            documents=parent_chunks,
            ids=[f"parent_{i}" for i in range(len(parent_chunks))],
        )

        return len(parent_chunks)

    def retrieve(self, query: str, document_id: int, top_k: int = 5) -> List[str]:
        try:
            child_col = self.client.get_collection(f"doc_{document_id}_child")
            parent_col = self.client.get_collection(f"doc_{document_id}_parent")
        except Exception:
            return []

        count = child_col.count()
        if count == 0:
            return []

        results = child_col.query(query_texts=[query], n_results=min(top_k, count))
        if (not results.get("metadatas") or not results["metadatas"]
                or not results["metadatas"][0]):
            return []

        parent_indices = set()
        for meta in results["metadatas"][0]:
            parent_indices.add(int(meta["parent_idx"]))

        if not parent_indices:
            return []

        parent_docs = parent_col.get(ids=[f"parent_{i}" for i in parent_indices])
        return parent_docs["documents"] if parent_docs.get("documents") else []

    def delete_document(self, document_id: int) -> None:
        for suffix in ("_child", "_parent"):
            try:
                self.client.delete_collection(f"doc_{document_id}{suffix}")
            except Exception:
                pass

    def _find_parent_chunk(self, child_text: str, parent_chunks: List[str]) -> int:
        for i, parent in enumerate(parent_chunks):
            if child_text[:50] in parent:
                return i
        return 0
