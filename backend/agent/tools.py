from typing import List
from rag.retriever import get_retriever
from core.config import settings


def retrieve_from_document(query: str, document_id: int,
                           strategy: str = None) -> str:
    s = strategy or settings.default_rag_strategy
    retriever = get_retriever(s)
    results = retriever.retrieve(query, document_id)
    if not results:
        return "未找到相关内容，请尝试换个角度检索。"
    return "\n\n---\n\n".join(results)


def get_document_summary(document_id: int) -> str:
    from rag.strategies.routing import RoutingRetriever
    retriever = RoutingRetriever()
    results = retriever._summary_retrieve(document_id, top_k=5)
    if not results:
        return "无法获取文档摘要，文档可能未索引。"
    return "\n\n".join(results)


def web_search(query: str, max_results: int = 5) -> str:
    api_key = getattr(settings, 'web_search_api_key', None) or settings.openai_api_key
    if not api_key:
        return "联网搜索未配置（缺少 API Key），请仅使用文档内检索。提示：可设置 WEB_SEARCH_API_KEY 环境变量启用。"

    provider = getattr(settings, 'web_search_provider', 'tavily')

    if provider == 'tavily':
        return _tavily_search(query, api_key, max_results)
    elif provider == 'serpapi':
        return _serpapi_search(query, api_key, max_results)
    else:
        return f"未知的搜索服务商: {provider}"


def _tavily_search(query: str, api_key: str, max_results: int) -> str:
    import requests
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return f"未搜索到与「{query}」相关的外部信息。"
        return "\n\n---\n\n".join(
            f"标题: {r.get('title', 'N/A')}\n内容: {r.get('content', '')}\n来源: {r.get('url', 'N/A')}"
            for r in results
        )
    except Exception as e:
        return f"联网搜索失败: {e}"


def _serpapi_search(query: str, api_key: str, max_results: int) -> str:
    import requests
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "num": max_results},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        organic = data.get("organic_results", [])
        if not organic:
            return f"未搜索到与「{query}」相关的外部信息。"
        return "\n\n---\n\n".join(
            f"标题: {r.get('title', 'N/A')}\n摘要: {r.get('snippet', '')}\n链接: {r.get('link', 'N/A')}"
            for r in organic
        )
    except Exception as e:
        return f"联网搜索失败: {e}"


def rewrite_search_query(original_query: str) -> str:
    """用 LLM 把用户口语改写为检索关键词，失败则返回原查询"""
    try:
        from core.llm_client import get_llm_client
        client = get_llm_client()
        response = client.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"将以下用户问题改写为2-3个适合文档检索的查询短语，"
                    f"用分号隔开。只输出查询短语，不要解释。\n\n"
                    f"用户问题：{original_query}"
                ),
            }],
            system="你是一个搜索查询优化助手。"
        )
        rewritten = (response.get("content") or "").strip()
        if rewritten:
            return rewritten
    except Exception:
        pass

    return original_query


def get_user_preferences(user_id: int) -> str:
    from agent.memory import get_long_term_memory
    prefs = get_long_term_memory(user_id)
    if not prefs:
        return "该用户暂无历史偏好记录。"
    return prefs


def save_user_preferences(user_id: int, prompt: str,
                          slide_structure: dict) -> str:
    from agent.memory import save_long_term_memory
    save_long_term_memory(user_id, prompt, slide_structure)
    return "用户偏好已记录。"


# ========== 工具 Schema（给 LLM Function Calling 用） ==========

TOOL_SCHEMAS = [
    {
        "name": "retrieve_from_document",
        "description": (
            "从用户上传的文档中检索与查询相关的内容片段。"
            "当需要查找文档中的具体信息时使用。"
            "提示：先用不同的关键词尝试检索，如果结果不够，可以换个角度重新检索。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词或问题。建议先用改写后的精确关键词检索，例如'市场份额数据'而非'这个公司怎么样'"
                },
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_document_summary",
        "description": "获取文档的整体摘要和主要内容概述。适合在开始时了解文档全貌，帮助确定后续检索方向。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "web_search",
        "description": (
            "联网搜索外部信息，补充文档中没有的内容。"
            "使用场景：文档内容不足以支撑PPT时，搜索行业数据、竞品动态、市场趋势等。"
            "注意：优先使用文档内检索，只在确实需要外部信息时才调用此工具。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，例如'2024年新能源汽车市场份额'"
                },
            },
            "required": ["query"]
        }
    },
    {
        "name": "rewrite_search_query",
        "description": (
            "将用户的需求改写为更适合文档检索的查询短语。"
            "当直接使用用户原话检索效果不佳时，使用此工具生成更好的检索查询。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "original_query": {
                    "type": "string",
                    "description": "用户的原始问题或需求描述"
                },
            },
            "required": ["original_query"]
        }
    },
    {
        "name": "get_user_preferences",
        "description": "获取当前用户的PPT历史偏好（常用模板风格、偏好结构等），用于个性化生成。",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID"
                },
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "save_user_preferences",
        "description": "保存用户的PPT偏好，用于下次生成时个性化推荐。在PPT生成成功后调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID"
                },
                "prompt": {
                    "type": "string",
                    "description": "本次生成prompt"
                },
                "slide_structure": {
                    "type": "object",
                    "description": "生成的幻灯片结构（slide的简要信息）"
                },
            },
            "required": ["user_id", "prompt", "slide_structure"]
        }
    },
]

TOOL_FUNCTIONS = {
    "retrieve_from_document": retrieve_from_document,
    "get_document_summary": get_document_summary,
    "web_search": web_search,
    "rewrite_search_query": rewrite_search_query,
    "get_user_preferences": get_user_preferences,
    "save_user_preferences": save_user_preferences,
}
