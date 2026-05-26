import json
import time
from typing import Dict, List, Optional, Tuple
from collections import OrderedDict


# ========== 短期记忆 ==========

class ShortTermMemory:
    """会话缓存，TTL 自动过期"""

    def __init__(self, max_entries: int = 50, ttl_seconds: int = 3600):
        self._store: OrderedDict[str, Tuple[float, any]] = OrderedDict()
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds

    def put(self, key: str, value: any):
        self._clean_expired()
        if len(self._store) >= self.max_entries:
            self._store.popitem(last=False)
        self._store[key] = (time.time(), value)

    def get(self, key: str) -> Optional[any]:
        self._clean_expired()
        entry = self._store.get(key)
        if entry:
            ts, value = entry
            if time.time() - ts > self.ttl_seconds:
                del self._store[key]
                return None
            return value
        return None

    def get_recent(self, n: int = 10) -> List[dict]:
        self._clean_expired()
        items = list(self._store.items())[-n:]
        return [{"key": k, "value": v[1]} for k, v in items]

    def clear(self):
        self._store.clear()

    def keys(self) -> list:
        self._clean_expired()
        return list(self._store.keys())

    def _clean_expired(self):
        now = time.time()
        expired = [
            k for k, (ts, _) in self._store.items()
            if now - ts > self.ttl_seconds
        ]
        for k in expired:
            del self._store[k]


_short_term_memory = ShortTermMemory()


def get_short_term_memory() -> ShortTermMemory:
    return _short_term_memory


# ========== 长期记忆（向量化） ==========

class LongTermMemory:
    """用户偏好向量化存入 ChromaDB，跨会话复用

    把用户对风格、结构的偏好归档，下次做 PPT 时注入 prompt 实现个性化。
    """

    COLLECTION_NAME = "user_preferences"

    def __init__(self, chroma_dir: str = "./chroma_db"):
        import chromadb
        self.client = chromadb.PersistentClient(path=chroma_dir)

    def _get_collection(self):
        return self.client.get_or_create_collection(name=self.COLLECTION_NAME)

    def save_preference(self, user_id: int, prompt: str,
                        slide_structure: dict, metadata: dict = None):
        collection = self._get_collection()

        preference_text = self._serialize_preference(prompt, slide_structure, metadata)

        existing = collection.get(ids=[f"user_{user_id}"])
        prev_meta = {}
        if existing and existing.get("metadatas"):
            prev_meta = existing["metadatas"][0] or {}
        if existing and existing.get("documents"):
            preference_text = existing["documents"][0] + "\n\n" + preference_text

        collection.upsert(
            documents=[preference_text],
            metadatas=[{
                "user_id": user_id,
                "last_updated": time.time(),
                "total_sessions": prev_meta.get("total_sessions", 0) + 1,
                **(metadata or {}),
            }],
            ids=[f"user_{user_id}"],
        )

    def get_preferences(self, user_id: int) -> Optional[str]:
        collection = self._get_collection()
        try:
            result = collection.get(ids=[f"user_{user_id}"])
            if result and result["documents"]:
                return result["documents"][0]
        except Exception:
            pass
        return None

    def search_similar_preferences(self, query: str, top_k: int = 3) -> List[str]:
        """新用户没有历史，检索相似用户的偏好做推荐"""
        collection = self._get_collection()
        if collection.count() == 0:
            return []
        try:
            results = collection.query(query_texts=[query], n_results=min(top_k, collection.count()))
            return results.get("documents", [[]])[0] if results.get("documents") else []
        except Exception:
            return []

    def delete_preferences(self, user_id: int):
        collection = self._get_collection()
        try:
            collection.delete(ids=[f"user_{user_id}"])
        except Exception:
            pass

    def _serialize_preference(self, prompt: str, slide_structure: dict,
                              metadata: dict = None) -> str:
        slides = slide_structure.get("slides", [])
        slide_count = len(slides)
        types = [s.get("type", "content") for s in slides]

        bullet_counts = [
            len(s.get("bullets", []) + s.get("key_points", []))
            for s in slides if s.get("type") not in ("title",)
        ]
        avg_bullets = sum(bullet_counts) / len(bullet_counts) if bullet_counts else 3

        parts = [
            f"用户需求: {prompt}",
            f"PPT标题: {slide_structure.get('title', '未知')}",
            f"幻灯片数量: {slide_count} 张",
            f"使用类型: {', '.join(set(types))}",
            f"平均要点数: {avg_bullets:.1f} 个/页",
        ]

        if metadata:
            parts.append(f"额外信息: {json.dumps(metadata, ensure_ascii=False)}")

        return "；".join(parts)


_long_term_memory = None


def get_long_term_memory_instance(chroma_dir: str = "./chroma_db") -> LongTermMemory:
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory(chroma_dir)
    return _long_term_memory


# ========== 对外接口 ==========

def get_conversation_context(session_id: str) -> Optional[dict]:
    memory = get_short_term_memory()
    return memory.get(f"session_{session_id}")


def save_conversation_context(session_id: str, context: dict):
    memory = get_short_term_memory()
    memory.put(f"session_{session_id}", context)


def get_long_term_memory(user_id: int) -> Optional[str]:
    memory = get_long_term_memory_instance()
    return memory.get_preferences(user_id)


def save_long_term_memory(user_id: int, prompt: str,
                          slide_structure: dict, metadata: dict = None):
    memory = get_long_term_memory_instance()
    memory.save_preference(user_id, prompt, slide_structure, metadata)


def clear_session(session_id: str):
    memory = get_short_term_memory()
    memory.put(f"session_{session_id}", {})
