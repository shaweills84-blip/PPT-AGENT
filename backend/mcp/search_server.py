from mcp.base import MCPServer


def create_search_server() -> MCPServer:
    server = MCPServer(
        name="search",
        description="联网搜索服务，提供网页搜索和新闻搜索能力"
    )

    @server.tool(
        description=(
            "搜索互联网上的公开信息。用于补充文档中没有的外部数据，"
            "如行业趋势、市场份额、竞品动态、最新新闻等。"
            "返回搜索结果列表（标题、内容摘要、来源链接）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询，建议使用精确的关键词组合，例如'2024新能源汽车销量排名'"
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回的最大结果数，默认5",
                    "default": 5,
                },
            },
            "required": ["query"],
        }
    )
    def web_search(query: str, max_results: int = 5) -> str:
        from agent.tools import web_search as _web_search
        return _web_search(query, max_results)

    @server.tool(
        description="搜索最新新闻资讯。适合查找最近的行业动态、公司公告、产品发布等信息。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "新闻搜索关键词"
                },
            },
            "required": ["query"],
        }
    )
    def news_search(query: str) -> str:
        from agent.tools import web_search as _web_search
        return _web_search(f"{query} 最新新闻 2025", max_results=5)

    return server
