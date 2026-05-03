from typing import List
from rag.base import BaseRetriever
from rag.utils.chunker import chunk_document
from core.config import settings
import chromadb


class BasicRetriever(BaseRetriever):

    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)

    def index_document(self, document_id: int, file_path: str) -> int:
        chunks = chunk_document(file_path)
        if not chunks:
            return 0

        collection = self.client.get_or_create_collection(
            name=f"doc_{document_id}",
        )

        # ChromaDB 内置 embedding 自动向量化
        collection.add(
            documents=chunks,
            ids=[f"chunk_{i}" for i in range(len(chunks))],
        )
        return len(chunks)

    def retrieve(self, query: str, document_id: int, top_k: int = 5) -> List[str]:
        try:
            collection = self.client.get_collection(f"doc_{document_id}")
        except Exception:
            return []

        count = collection.count()
        if count == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
        )
        if not results.get("documents") or not results["documents"][0]:
            return []
        return results["documents"][0]

    def delete_document(self, document_id: int) -> None:
        try:
            self.client.delete_collection(f"doc_{document_id}")
        except Exception:
            pass
