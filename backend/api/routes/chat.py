import os
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import User
from db.crud import create_task, update_task_status
from db.schemas import TaskCreate
from api.dependencies import get_current_user
from core.config import settings
from core.llm_client import get_llm_client
from agent.conversation import get_conversation_manager
from agent.utils import try_extract_ppt_structure
from agent.orchestrator import PPTOrchestrator
from mcp.manager import get_mcp_manager
from ppt.generator import generate_from_dict

router = APIRouter(tags=["对话式生成"])


class SessionCreateRequest(BaseModel):
    document_id: int
    rag_strategy: str = "basic"


class SessionCreateResponse(BaseModel):
    session_id: str
    message: str


class MessageRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    reply: str
    stage: str
    ppt_preview: Optional[dict] = None


class GenerateResponse(BaseModel):
    session_id: str
    task_id: int
    ppt_data: dict


class SessionListItem(BaseModel):
    session_id: str
    document_id: int
    stage: str
    preview: str
    created_at: float
    updated_at: float


# ========== 会话 ==========

@router.post("/chat/sessions", response_model=SessionCreateResponse)
async def create_chat_session(
    req: SessionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from db.crud import get_document
    doc = get_document(db, req.document_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404, "文档不存在")
    if doc.status != "ready":
        raise HTTPException(400, f"文档状态为 {doc.status}，无法使用")

    prefs = ""
    if settings.enable_memory:
        from agent.memory import get_long_term_memory
        prefs = get_long_term_memory(user.id) or ""

    mgr = get_conversation_manager()
    session_id = mgr.create_session(
        user_id=user.id,
        document_id=req.document_id,
        user_preferences=prefs,
        rag_strategy=req.rag_strategy or "basic",
    )

    welcome = "你好！我已经读取了你的文档。请告诉我你想做什么样的 PPT？比如：主题、侧重点、风格要求等。"
    mgr.add_agent_message(session_id, welcome, stage="clarifying")

    return SessionCreateResponse(session_id=session_id, message=welcome)


@router.get("/chat/sessions", response_model=list[SessionListItem])
async def list_sessions(user: User = Depends(get_current_user)):
    mgr = get_conversation_manager()
    sessions = mgr.list_user_sessions(user.id)

    result = []
    for s in sessions:
        messages = s.get("messages", [])
        preview = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                preview = m["content"][:50]
                break
        if not preview:
            preview = "(新会话)"

        result.append(SessionListItem(
            session_id=s["session_id"],
            document_id=s.get("document_id", 0),
            stage=s.get("stage", "clarifying"),
            preview=preview,
            created_at=s.get("created_at", 0),
            updated_at=s.get("updated_at", 0),
        ))

    result.sort(key=lambda x: x.updated_at, reverse=True)
    return result


@router.get("/chat/sessions/{session_id}")
async def get_session(session_id: str, user: User = Depends(get_current_user)):
    mgr = get_conversation_manager()
    ctx = mgr.get_session(session_id)
    if not ctx:
        raise HTTPException(404, "会话不存在或已过期")
    if ctx.get("user_id") != user.id:
        raise HTTPException(403, "无权访问此会话")

    return {
        "session_id": session_id,
        "document_id": ctx.get("document_id"),
        "messages": ctx.get("messages", []),
        "clarification": mgr.get_clarification_state(session_id),
        "ppt_draft": ctx.get("ppt_draft"),
        "stage": ctx.get("stage"),
        "task_id": ctx.get("task_id"),
    }


# ========== 核心：对话 ==========

@router.post("/chat/sessions/{session_id}/message", response_model=MessageResponse)
async def send_message(
    session_id: str,
    req: MessageRequest,
    user: User = Depends(get_current_user),
):
    mgr = get_conversation_manager()
    ctx = mgr.get_session(session_id)
    if not ctx:
        raise HTTPException(404, "会话不存在或已过期")
    if ctx.get("user_id") != user.id:
        raise HTTPException(403, "无权访问此会话")

    # 保存 add_user_message 之前的 stage（add_user_message 会重置为 clarifying）
    prev_stage = ctx.get("stage", "clarifying")

    mgr.add_user_message(session_id, req.content)

    client = get_llm_client()
    system_prompt = mgr.build_chat_system_prompt(session_id)
    messages = mgr.build_agent_messages(session_id)

    current_stage = prev_stage
    if current_stage in ("done", "generating") and ctx.get("ppt_draft"):
        ppt_summary = json.dumps(ctx["ppt_draft"], ensure_ascii=False)
        system_prompt += (
            f"\n\n## 当前 PPT 已生成\n"
            f"以下 PPT 已被用户确认生成，用户可能想修改它：\n{ppt_summary[:800]}\n\n"
            f"如果用户要求修改，请理解修改意图后提出具体的修改方案。"
        )

    # clarifying 阶段不给工具：agent 专心跟用户聊天澄清需求
    # confirmed 阶段给工具：agent 检索文档后给出具体 PPT 结构建议
    # done/generating 阶段不给工具：基于已有 PPT 结构回复修改意见
    give_tools = current_stage in ("confirmed",)
    tools = _get_tools_for_chat(ctx.get("document_id", 0), ctx.get("rag_strategy", "basic")) if give_tools else []

    max_rounds = 4 if not tools else 8
    for _ in range(max_rounds):
        response = client.chat(
            messages=messages,
            system=system_prompt,
            tools=tools,
        )

        content = response["content"] or ""
        tool_calls = response["tool_calls"]

        if not tool_calls or response["stop_reason"] != "tool_use":
            ppt_preview = try_extract_ppt_structure(content)

            if ppt_preview and ppt_preview.get("slides"):
                stage = "confirmed"
                mgr.add_agent_message(session_id, content, ppt_draft=ppt_preview, stage=stage)
            else:
                # 保持之前的 stage（done 阶段修改后还是 done，confirmed 还是 confirmed）
                stage = prev_stage if prev_stage in ("done", "confirmed") else ctx.get("stage", "clarifying")
                mgr.add_agent_message(session_id, content, stage=stage)

            return MessageResponse(
                reply=content,
                stage=stage,
                ppt_preview=ppt_preview,
            )

        assistant_msg = {"role": "assistant", "content": content}
        if response.get("raw_tool_calls"):
            assistant_msg["tool_calls"] = response["raw_tool_calls"]
        messages.append(assistant_msg)

        for tc in tool_calls:
            result = _execute_chat_tool(
                tc, ctx.get("document_id", 0), ctx.get("rag_strategy", "basic"),
                session_id=session_id,
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    fallback = "抱歉，我暂时无法处理你的请求。能否换个方式描述你的需求？"
    mgr.add_agent_message(session_id, fallback)
    return MessageResponse(reply=fallback, stage="clarifying")


# ========== 核心：生成 ==========

@router.post("/chat/sessions/{session_id}/generate")
async def generate_from_chat(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mgr = get_conversation_manager()
    ctx = mgr.get_session(session_id)
    if not ctx:
        raise HTTPException(404, "会话不存在或已过期")
    if ctx.get("user_id") != user.id:
        raise HTTPException(403, "无权访问此会话")

    document_id = ctx["document_id"]
    strategy = ctx.get("rag_strategy", "basic")

    clarification = mgr.get_clarification_state(session_id)
    context = {
        "clarified": clarification.get("clarified", {}),
        "preferences": ctx.get("user_preferences", ""),
        "messages": ctx.get("messages", []),
        "retrieval_cache": ctx.get("retrieval_cache", {}),
    }

    mgr.add_agent_message(session_id, "正在分析文档并生成 PPT，请稍候...", stage="generating")

    try:
        orch = PPTOrchestrator()
        result = orch.run(
            context=context,
            document_id=document_id,
            strategy=strategy,
            enable_web_search=False,
        )
    except Exception as e:
        import traceback, datetime, sys
        tb = traceback.format_exc()
        # 写入 error.log
        try:
            with open("error.log", "a") as f:
                f.write(f"\n[{datetime.datetime.now().isoformat()}] GENERATE ERROR\n{tb}\n")
        except Exception:
            pass
        # 把最后一行 traceback 附在错误信息里方便调试
        last_line = tb.strip().split('\n')[-1] if tb else str(e)
        raise HTTPException(500, f"生成失败: {type(e).__name__}: {e} | last_frame: {last_line}")

    ppt_data = result["slides"]

    if not ppt_data or not ppt_data.get("slides"):
        raise HTTPException(400, "生成失败，请重新与 Agent 澄清需求后再试")

    task = create_task(db, user.id, TaskCreate(
        document_id=document_id,
        prompt="[对话式生成] " + json.dumps(clarification, ensure_ascii=False),
        rag_strategy=strategy,
    ))

    try:
        update_task_status(db, task.id, "running")
        output_path = os.path.join(settings.output_dir, f"task_{task.id}.pptx")
        generate_from_dict(ppt_data, output_path)
        update_task_status(db, task.id, "done", result_path=output_path)

        if settings.enable_memory:
            from agent.memory import save_long_term_memory
            save_long_term_memory(user.id, "[对话模式]", ppt_data)

        mgr.set_ppt_draft(session_id, ppt_data)
        mgr.add_agent_message(
            session_id,
            f"PPT 已生成完成！共 {len(ppt_data['slides'])} 页。你可以下载，也可以继续告诉我需要修改的地方。",
            ppt_draft=ppt_data,
            stage="done",
        )

        mgr.set_task_id(session_id, task.id)

    except Exception as e:
        import traceback, datetime
        tb = traceback.format_exc()
        try:
            with open("error.log", "a") as f:
                f.write(f"\n[{datetime.datetime.now().isoformat()}] PPTX GENERATE ERROR\n{tb}\n")
        except Exception:
            pass
        update_task_status(db, task.id, "failed", error_msg=str(e))
        last_line = tb.strip().split('\n')[-1] if tb else str(e)
        raise HTTPException(500, f"生成失败: {type(e).__name__}: {e} | last: {last_line}")

    return GenerateResponse(
        session_id=session_id,
        task_id=task.id,
        ppt_data=ppt_data,
    )


@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
):
    mgr = get_conversation_manager()
    ctx = mgr.get_session(session_id)
    if not ctx:
        raise HTTPException(404, "会话不存在")
    if ctx.get("user_id") != user.id:
        raise HTTPException(403, "无权操作")
    mgr.delete_session(session_id)
    return {"status": "deleted"}


CHAT_TOOL_NAMES = ("retrieve_from_document", "get_document_summary",
                    "web_search", "rewrite_search_query")


def _get_tools_for_chat(document_id: int, rag_strategy: str) -> list:
    return get_mcp_manager().get_tool_schemas(
        document_id=document_id,
        rag_strategy=rag_strategy,
        filter_names=list(CHAT_TOOL_NAMES),
    )


def _execute_chat_tool(tool_call: dict, document_id: int, rag_strategy: str,
                       session_id: str = None) -> str:
    name = tool_call["name"]
    args = tool_call["arguments"]

    if name == "retrieve_from_document" and session_id:
        query = args.get("query", "")
        mgr = get_conversation_manager()
        cached = mgr.get_cached_retrieval(session_id, query)
        if cached:
            return cached + "\n\n[来自缓存]"

        result = get_mcp_manager().execute_tool(
            name, args, document_id, rag_strategy,
        )
        mgr.cache_retrieval(session_id, query, result)
        return result

    return get_mcp_manager().execute_tool(name, args, document_id, rag_strategy)
