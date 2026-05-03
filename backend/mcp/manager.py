"""
MCP 统一管理层。

不管 MCP 开没开，chat.py / research_agent.py 都通过这里的接口获取工具：
  get_tool_schemas()  → LLM Function Calling 格式的工具列表
  execute_tool()      → 执行工具调用

当 enable_mcp=True 时走 MCP 协议发现和调用，否则回退到 agent.tools 的硬编码。
"""
from typing import List, Optional
from core.config import settings


class MCPManager:
    """MCP 生命周期管理，按请求创建 Server（因为 document_id 是动态的）"""

    def __init__(self):
        self._client = None
        self._init_done = False

    def _ensure_client(self):
        if self._init_done:
            return
        self._init_done = True
        if settings.enable_mcp:
            from mcp.base import MCPClient
            self._client = MCPClient()

    def _build_servers(self, document_id: int, rag_strategy: str,
                       enable_web_search: bool):
        """按请求参数创建 MCP Server 并连接到 Client"""
        if not self._client:
            return

        servers_config = [s.strip() for s in settings.mcp_servers.split(",") if s.strip()]

        if "retrieval" in servers_config:
            from mcp.retrieval_server import create_retrieval_server
            self._client.connect(create_retrieval_server(
                document_id=document_id,
                rag_strategy=rag_strategy,
            ))

        if "search" in servers_config and enable_web_search:
            from mcp.search_server import create_search_server
            self._client.connect(create_search_server())

    def get_tool_schemas(self, document_id: int, rag_strategy: str,
                         filter_names: List[str] = None,
                         enable_web_search: bool = False) -> List[dict]:
        """返回 OpenAI Function Calling 格式的工具列表"""
        self._ensure_client()

        if self._client:
            self._build_servers(document_id, rag_strategy, enable_web_search)
            schemas = self._client.get_tool_schemas_for_llm()

            if filter_names:
                schemas = [s for s in schemas if s["function"]["name"] in filter_names]

            if schemas:
                return self._annotate_schemas(schemas, document_id, rag_strategy)

        # 回退到硬编码工具
        return _build_tools_from_static(filter_names, document_id, rag_strategy)

    def execute_tool(self, name: str, arguments: dict,
                     document_id: int, rag_strategy: str) -> str:
        """执行工具调用，优先走 MCP，回退到硬编码"""
        self._ensure_client()

        if self._client:
            try:
                return self._client.call_tool(name, arguments)
            except Exception:
                pass

        # 回退
        return _execute_tool_static(name, arguments, document_id, rag_strategy)

    def _annotate_schemas(self, schemas: List[dict], document_id: int,
                          rag_strategy: str) -> List[dict]:
        """给检索工具的 description 注入文档 ID 和策略信息"""
        for s in schemas:
            name = s["function"]["name"]
            if name in ("retrieve", "retrieve_from_document"):
                desc = s["function"].get("description", "")
                s["function"]["description"] = (
                    f"{desc}（文档ID: {document_id}, 策略: {rag_strategy}）"
                )
        return schemas


# ---- 单例 ----

_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager()
    return _manager


# ---- 回退：硬编码工具（MCP 关闭时用） ----

def _build_tools_from_static(filter_names: List[str] = None,
                              document_id: int = 0,
                              rag_strategy: str = "basic") -> List[dict]:
    from agent.tools import TOOL_SCHEMAS
    import copy

    tools = []
    for schema in TOOL_SCHEMAS:
        name = schema["name"]
        if filter_names and name not in filter_names:
            continue

        s = copy.deepcopy(schema)
        desc = s["description"]
        if name == "retrieve_from_document":
            desc += f"（文档ID: {document_id}, 策略: {rag_strategy}）"

        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": s.get("input_schema", {}),
            }
        })
    return tools


def _execute_tool_static(name: str, arguments: dict,
                          document_id: int, rag_strategy: str) -> str:
    from agent.tools import TOOL_FUNCTIONS, retrieve_from_document

    if name == "retrieve_from_document":
        return retrieve_from_document(
            query=arguments.get("query", ""),
            document_id=document_id,
            strategy=rag_strategy,
        )
    elif name in TOOL_FUNCTIONS:
        fn = TOOL_FUNCTIONS[name]
        try:
            return fn(**arguments)
        except Exception as e:
            return f"工具执行失败: {e}"

    return f"未知工具: {name}"
