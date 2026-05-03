import json
from typing import Dict, Optional
from core.llm_client import get_llm_client
from agent.prompts import RESEARCH_AGENT_PROMPT


class ResearchAgent:
    """研究子 Agent —— 只负责找信息，多轮检索直到素材充分"""

    def __init__(self):
        self.client = get_llm_client()

    def research(self, prompt: str, document_id: int,
                 strategy: str = "basic",
                 enable_web_search: bool = False,
                 max_iterations: int = 6,
                 retrieval_cache: dict = None) -> dict:
        self._retrieval_cache = retrieval_cache or {}
        tools = self._build_tools(document_id, strategy, enable_web_search)

        user_message = (
            f"【研究任务】{prompt}\n\n"
            f"请深入研究文档内容，按以下步骤操作：\n"
            f"1. 先用不同关键词检索文档，覆盖所有可能相关的角度\n"
            f"2. 每轮检索后评估信息充分性，不足则改写查询重新检索\n"
            f"3. 提取关键数据和事实\n"
            f"4. 标注信息缺口\n"
            f"5. 输出结构化研究报告\n\n"
            f"文档ID: {document_id}"
        )

        messages = [{"role": "user", "content": user_message}]

        for iteration in range(max_iterations):
            response = self.client.chat(
                messages=messages,
                system=RESEARCH_AGENT_PROMPT,
                tools=tools,
            )

            content = response["content"] or ""
            stop_reason = response["stop_reason"]
            tool_calls = response["tool_calls"]

            if stop_reason != "tool_use" or not tool_calls:
                report = self._parse_report(content)
                if report:
                    return report
                messages.append({
                    "role": "user",
                    "content": "请继续研究，完成后再输出研究报告JSON。"
                })
                continue

            assistant_msg = {"role": "assistant", "content": content}
            if response.get("raw_tool_calls"):
                assistant_msg["tool_calls"] = response["raw_tool_calls"]
            messages.append(assistant_msg)

            for tc in tool_calls:
                result = self._execute_tool(tc, document_id, strategy)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        # 兜底
        messages.append({
            "role": "user",
            "content": "请立即输出你的研究结果JSON。不要调用工具。"
        })
        final = self.client.chat(messages=messages, system=RESEARCH_AGENT_PROMPT)
        return self._parse_report(final["content"] or "") or self._empty_report()

    RESEARCH_TOOL_NAMES = (
        "retrieve_from_document", "get_document_summary",
        "rewrite_search_query", "web_search",
    )

    def _build_tools(self, document_id: int, strategy: str,
                     enable_web_search: bool) -> list:
        from mcp.manager import get_mcp_manager
        names = list(self.RESEARCH_TOOL_NAMES)
        if not enable_web_search:
            names = [n for n in names if n != "web_search"]
        return get_mcp_manager().get_tool_schemas(
            document_id=document_id,
            rag_strategy=strategy,
            filter_names=names,
            enable_web_search=enable_web_search,
        )

    def _execute_tool(self, tool_call: dict, document_id: int,
                      strategy: str) -> str:
        from mcp.manager import get_mcp_manager
        name = tool_call["name"]
        args = tool_call["arguments"]

        if name == "retrieve_from_document":
            query = args.get("query", "")
            if query and hasattr(self, '_retrieval_cache'):
                cached = self._retrieval_cache.get(query)
                if cached:
                    return cached + "\n\n[来自对话缓存]"

        return get_mcp_manager().execute_tool(name, args, document_id, strategy)

    def _parse_report(self, content: str) -> Optional[dict]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        import re
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and start < end:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _empty_report(self) -> dict:
        return {
            "topic": "",
            "key_findings": [],
            "data_points": [],
            "dimensions": [],
            "knowledge_gaps": ["研究未完成"],
        }
