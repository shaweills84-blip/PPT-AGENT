import json
from abc import ABC, abstractmethod
from typing import Dict, List, Callable, Any


class MCPServer(ABC):
    """MCP Server 基类 — 封装工具，通过标准协议暴露给 Agent"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._tools: Dict[str, Dict] = {}

    def register_tool(self, name: str, description: str,
                      handler: Callable, input_schema: dict):
        self._tools[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "handler": handler,
        }

    def tool(self, name: str = None, description: str = "",
             input_schema: dict = None):
        """装饰器：将函数注册为 MCP 工具"""
        import inspect

        def decorator(fn: Callable):
            tool_name = name or fn.__name__
            schema = input_schema or _auto_schema(fn)
            self.register_tool(tool_name, description or fn.__doc__ or "", fn, schema)
            return fn

        return decorator

    def list_tools(self) -> List[dict]:
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"未知工具: {name}"})

        try:
            result = tool["handler"](**arguments)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"工具执行失败: {str(e)}"})


class MCPClient:
    """MCP Client — 连接多个 Server，为 Agent 提供统一的工具调用接口"""

    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}

    def connect(self, server: MCPServer):
        self._servers[server.name] = server

    def disconnect(self, server_name: str):
        self._servers.pop(server_name, None)

    def discover_tools(self) -> List[dict]:
        tools = []
        for server in self._servers.values():
            for tool in server.list_tools():
                tools.append({
                    **tool,
                    "server": server.name,
                })
        return tools

    def call_tool(self, name: str, arguments: dict) -> str:
        for server in self._servers.values():
            if name in [t["name"] for t in server.list_tools()]:
                return server.call_tool(name, arguments)
        return json.dumps({"error": f"未找到工具: {name}"})

    def get_tool_schemas_for_llm(self) -> List[dict]:
        """把 MCP 工具转成 OpenAI Function Calling 格式"""
        schemas = []
        for tool in self.discover_tools():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                }
            })
        return schemas


def _auto_schema(fn: Callable) -> dict:
    import inspect
    sig = inspect.signature(fn)
    properties = {}
    required = []
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            type_map = {int: "integer", float: "number", bool: "boolean", str: "string", list: "array", dict: "object"}
            param_type = type_map.get(param.annotation, "string")
        properties[param_name] = {"type": param_type, "description": f"{param_name} 参数"}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
