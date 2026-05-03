from mcp.base import MCPServer


def create_retrieval_server(document_id: int = None,
                            rag_strategy: str = "basic") -> MCPServer:
    server = MCPServer(
        name="retrieval",
        description="文档检索服务，提供文档内容检索、摘要获取、查询改写等功能"
    )

    @server.tool(
        name="retrieve_from_document",
        description=(
            "从用户上传的文档中检索与查询相关的内容片段。"
            "当需要查找文档中的具体信息时使用此工具。"
            "支持多种检索策略（关键词、语义、混合），自动选择最优策略。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询，建议使用具体的关键词而非完整的自然语言问题"
                },
            },
            "required": ["query"],
        }
    )
    def retrieve_from_document(query: str) -> str:
        from agent.tools import retrieve_from_document as _retrieve
        doc_id = document_id or 0
        return _retrieve(query=query, document_id=doc_id, strategy=rag_strategy)

    @server.tool(
        name="get_document_summary",
        description=(
            "获取文档的整体摘要和主要内容概述。"
            "适合在PPT制作的初始阶段使用，帮助建立对文档内容的整体认知。"
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        }
    )
    def get_document_summary() -> str:
        from agent.tools import get_document_summary as _summary
        doc_id = document_id or 0
        return _summary(doc_id)

    @server.tool(
        name="rewrite_search_query",
        description=(
            "将用户的自然语言需求改写为更适合检索的查询短语。"
            "当直接用用户原话检索效果不佳时，使用此工具生成更好的检索查询。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "original_query": {
                    "type": "string",
                    "description": "需要改写的原始查询"
                },
            },
            "required": ["original_query"],
        }
    )
    def rewrite_search_query(original_query: str) -> str:
        from agent.tools import rewrite_search_query as _rewrite
        return _rewrite(original_query)

    return server
