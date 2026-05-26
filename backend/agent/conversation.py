import json
import time
import uuid
from typing import Dict, List, Optional, Any
from agent.memory import get_short_term_memory
from agent.prompts import SYSTEM_PROMPT


class ConversationManager:
    """对话状态管理。热层用 ShortTermMemory，冷层写 MySQL。

    read: 内存命中直接返回，未命中查 DB 回填
    write: 先写内存，同步写 DB（失败降级不阻塞对话）

    session_context 结构:
      user_id, document_id, messages[], clarified{}, pending[],
      retrieval_cache{}, ppt_draft, stage
    """

    STAGE_CLARIFYING = "clarifying"
    STAGE_CONFIRMED = "confirmed"
    STAGE_GENERATING = "generating"
    STAGE_DONE = "done"

    def __init__(self):
        self._memory = get_short_term_memory()

    def create_session(self, user_id: int, document_id: int,
                       user_preferences: str = "", rag_strategy: str = "basic") -> str:
        session_id = str(uuid.uuid4())[:8]

        context = {
            "user_id": user_id,
            "document_id": document_id,
            "rag_strategy": rag_strategy,
            "user_preferences": user_preferences,
            "messages": [],
            "clarified": {},
            "pending": ["主题", "侧重点", "页数风格"],
            "retrieval_cache": {},
            "ppt_draft": None,
            "stage": self.STAGE_CLARIFYING,
            "created_at": time.time(),
        }

        self._db_persist(session_id, context)
        self._save(session_id, context)
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        ctx = self._memory.get(f"session_{session_id}")
        if ctx:
            return ctx

        db_ctx = self._db_load(session_id)
        if db_ctx:
            self._memory.put(f"session_{session_id}", db_ctx)
            return db_ctx
        return None

    def delete_session(self, session_id: str):
        self._memory.put(f"session_{session_id}", {})
        self._db_delete(session_id)

    def list_user_sessions(self, user_id: int) -> list:
        db_sessions = self._db_list(user_id)
        result = []
        for s in db_sessions:
            result.append({
                "session_id": s.session_id,
                "user_id": s.user_id,
                "document_id": s.document_id,
                "rag_strategy": s.rag_strategy,
                "messages": json.loads(s.messages or "[]"),
                "clarified": json.loads(s.clarified or "{}"),
                "retrieval_cache": json.loads(s.retrieval_cache or "{}"),
                "ppt_draft": json.loads(s.ppt_draft) if s.ppt_draft else None,
                "stage": s.stage,
                "user_preferences": s.user_preferences or "",
                "task_id": s.task_id,
                "created_at": s.created_at.timestamp() if s.created_at else 0,
                "updated_at": s.updated_at.timestamp() if s.updated_at else 0,
            })
        return result

    def add_user_message(self, session_id: str, content: str) -> dict:
        ctx = self.get_session(session_id)
        if not ctx:
            return {}

        ctx["messages"].append({"role": "user", "content": content})
        ctx["stage"] = self.STAGE_CLARIFYING
        self._update_clarification_state(ctx, content)

        self._save(session_id, ctx)
        return ctx

    def add_agent_message(self, session_id: str, content: str,
                          ppt_draft: dict = None, stage: str = None):
        ctx = self.get_session(session_id)
        if not ctx:
            return

        ctx["messages"].append({"role": "assistant", "content": content})

        if ppt_draft:
            ctx["ppt_draft"] = ppt_draft
        if stage:
            ctx["stage"] = stage

        self._save(session_id, ctx)

    def add_tool_results(self, session_id: str, results: List[dict]):
        ctx = self.get_session(session_id)
        if not ctx:
            return

        for r in results:
            ctx["messages"].append({"role": "tool", "content": r["content"],
                                     "tool_name": r.get("tool_name", "")})

        self._save(session_id, ctx)

    def cache_retrieval(self, session_id: str, query: str, result: str):
        ctx = self.get_session(session_id)
        if not ctx:
            return
        ctx["retrieval_cache"][query] = result
        self._save(session_id, ctx)

    def get_cached_retrieval(self, session_id: str, query: str) -> Optional[str]:
        ctx = self.get_session(session_id)
        if not ctx:
            return None
        return ctx.get("retrieval_cache", {}).get(query)

    def get_clarification_state(self, session_id: str) -> dict:
        ctx = self.get_session(session_id)
        if not ctx:
            return {"clarified": {}, "pending": []}
        return {
            "clarified": ctx.get("clarified", {}),
            "pending": ctx.get("pending", []),
            "stage": ctx.get("stage", self.STAGE_CLARIFYING),
        }

    def is_ready_to_generate(self, session_id: str) -> bool:
        ctx = self.get_session(session_id)
        if not ctx:
            return False
        return bool(ctx.get("clarified", {}).get("topic"))

    def confirm_clarifications(self, session_id: str, updates: dict):
        ctx = self.get_session(session_id)
        if not ctx:
            return
        ctx["clarified"].update(updates)
        ctx["pending"] = [p for p in ctx.get("pending", [])
                          if p not in updates]
        if not ctx["pending"]:
            ctx["stage"] = self.STAGE_CONFIRMED
        self._save(session_id, ctx)

    def build_agent_messages(self, session_id: str) -> List[dict]:
        ctx = self.get_session(session_id)
        if not ctx:
            return []

        messages = list(ctx.get("messages", []))

        prefs = ctx.get("user_preferences", "")
        if prefs and messages:
            messages[0]["content"] += f"\n\n[用户历史偏好] {prefs}"

        return messages

    def build_chat_system_prompt(self, session_id: str) -> str:
        ctx = self.get_session(session_id)
        if not ctx:
            return SYSTEM_PROMPT

        state = self.get_clarification_state(session_id)
        clarified_str = json.dumps(state["clarified"], ensure_ascii=False) if state["clarified"] else "尚未明确"
        pending_str = "、".join(state["pending"]) if state["pending"] else "无"

        prompt = SYSTEM_PROMPT + f"""
## 当前对话状态

已确认的信息：{clarified_str}
还需确认的信息：{pending_str}
对话阶段：{state['stage']}
文档ID：{ctx.get('document_id')}

根据以上状态决定你的下一步行动：
- 如果还有待确认信息（pending 非空），继续追问用户，每次1-2个问题
- 如果信息已充分，简洁说明你打算按什么结构组织PPT（3-5条大纲），请用户确认
- 如果用户已确认结构，告诉用户「可以点击生成按钮开始制作」
- 重要：你在这个阶段只需要和用户对话，不需要检索文档。检索和PPT生成由后台系统自动完成。
- 每轮回复2-4句话，不要过长。
"""
        return prompt

    def get_ppt_draft(self, session_id: str) -> Optional[dict]:
        ctx = self.get_session(session_id)
        return ctx.get("ppt_draft") if ctx else None

    def set_ppt_draft(self, session_id: str, draft: dict):
        ctx = self.get_session(session_id)
        if ctx:
            ctx["ppt_draft"] = draft
            self._save(session_id, ctx)

    def set_task_id(self, session_id: str, task_id: int):
        ctx = self.get_session(session_id)
        if ctx:
            ctx["task_id"] = task_id
            self._save(session_id, ctx)

    def _save(self, session_id: str, context: dict):
        context["updated_at"] = time.time()
        self._memory.put(f"session_{session_id}", context)

        try:
            self._db_persist(session_id, context)
        except Exception:
            pass  # DB 挂了降级，不阻塞对话

    def _get_db(self):
        from db.session import SessionLocal
        return SessionLocal()

    def _db_persist(self, session_id: str, context: dict):
        from db.crud import get_chat_session, create_chat_session, update_chat_session

        db = self._get_db()
        try:
            existing = get_chat_session(db, session_id)
            if existing:
                update_chat_session(db, session_id,
                    messages=json.dumps(context.get("messages", []), ensure_ascii=False),
                    clarified=json.dumps(context.get("clarified", {}), ensure_ascii=False),
                    retrieval_cache=json.dumps(context.get("retrieval_cache", {}), ensure_ascii=False),
                    ppt_draft=json.dumps(context["ppt_draft"], ensure_ascii=False) if context.get("ppt_draft") else None,
                    stage=context.get("stage", "clarifying"),
                    task_id=context.get("task_id"),
                )
            else:
                create_chat_session(db,
                    session_id=session_id,
                    user_id=context["user_id"],
                    document_id=context["document_id"],
                    rag_strategy=context.get("rag_strategy", "basic"),
                    user_preferences=context.get("user_preferences", ""),
                )
        finally:
            db.close()

    def _db_load(self, session_id: str) -> Optional[dict]:
        from db.crud import get_chat_session

        db = self._get_db()
        try:
            s = get_chat_session(db, session_id)
            if not s:
                return None
            return {
                "user_id": s.user_id,
                "document_id": s.document_id,
                "rag_strategy": s.rag_strategy,
                "user_preferences": s.user_preferences or "",
                "messages": json.loads(s.messages or "[]"),
                "clarified": json.loads(s.clarified or "{}"),
                "pending": [],
                "retrieval_cache": json.loads(s.retrieval_cache or "{}"),
                "ppt_draft": json.loads(s.ppt_draft) if s.ppt_draft else None,
                "stage": s.stage,
                "task_id": s.task_id,
                "created_at": s.created_at.timestamp() if s.created_at else time.time(),
                "updated_at": s.updated_at.timestamp() if s.updated_at else time.time(),
            }
        finally:
            db.close()

    def _db_delete(self, session_id: str):
        from db.crud import delete_chat_session

        db = self._get_db()
        try:
            delete_chat_session(db, session_id)
        finally:
            db.close()

    def _db_list(self, user_id: int) -> list:
        from db.crud import list_user_chat_sessions

        db = self._get_db()
        try:
            return list_user_chat_sessions(db, user_id)
        finally:
            db.close()

    def _update_clarification_state(self, ctx: dict, user_message: str):
        """从用户消息中快速提取意图要素"""
        msg_lower = user_message.lower()

        pending = ctx.get("pending", [])
        if "主题" in pending and len(user_message) > 5:
            ctx["clarified"]["topic"] = user_message[:100]
            pending.remove("主题")

        if "侧重点" in pending:
            if any(kw in msg_lower for kw in [
                "分析", "对比", "报告", "总结", "介绍", "科普", "复盘",
                "侧重", "重点", "方面", "都要", "每个",
            ]):
                ctx["clarified"]["focus"] = user_message[:100]
                pending.remove("侧重点")

        if "页数风格" in pending:
            if any(kw in msg_lower for kw in [
                "页", "风格", "详细", "简洁", "专业", "通俗", "页数",
            ]):
                ctx["clarified"]["style"] = user_message[:100]
                pending.remove("页数风格")

        ctx["pending"] = pending
        if not pending:
            ctx["stage"] = self.STAGE_CONFIRMED


_conversation_manager = ConversationManager()


def get_conversation_manager() -> ConversationManager:
    return _conversation_manager
