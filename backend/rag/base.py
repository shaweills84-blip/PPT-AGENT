from abc import ABC, abstractmethod
from typing import List


class BaseRetriever(ABC):

    @abstractmethod
    def retrieve(self, query: str, document_id: int, top_k: int = 5) -> List[str]:
        pass

    @abstractmethod
    def index_document(self, document_id: int, file_path: str) -> int:
        pass

    @abstractmethod
    def delete_document(self, document_id: int) -> None:
        pass
