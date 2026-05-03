from typing import List, Dict, Any, Optional
from core.config import settings


def get_llm_client() -> "BaseLLMClient":
    provider = settings.llm_provider
    if provider == "openai":
        return OpenAIClient()
    elif provider == "anthropic":
        return AnthropicClient()
    elif provider == "mimo":
        return MiMoClient()
    elif provider == "deepseek":
        return DeepSeekClient()
    elif provider == "qwen":
        return QwenClient()
    else:
        raise ValueError(f"未知的 LLM 提供商: {provider}")


class BaseLLMClient:
    """统一返回格式: {"content": str, "tool_calls": list | None, "stop_reason": str, "raw": object}"""

    def chat(self, messages: List[Dict], system: str = "",
             tools: List[Dict] = None) -> Dict:
        raise NotImplementedError

    def execute_tool_call(self, tool_call: dict) -> str:
        raise NotImplementedError


class OpenAIClient(BaseLLMClient):

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=self._get_api_key(),
            base_url=self._get_base_url(),
        )
        self.model = self._get_model()

    def _get_api_key(self) -> str:
        return settings.openai_api_key

    def _get_base_url(self) -> str | None:
        return None

    def _get_model(self) -> str:
        return settings.openai_model

    def chat(self, messages: List[Dict], system: str = "",
             tools: List[Dict] = None) -> Dict:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if system:
            kwargs["messages"] = [{"role": "system", "content": system}] + messages
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        if not response.choices:
            raise RuntimeError(f"LLM 返回空 choices: {response}")
        msg = response.choices[0].message

        # debug log — 生产环境可注释掉
        with open("llm_debug.log", "a", encoding="utf-8") as f:
            f.write(f"finish_reason: {response.choices[0].finish_reason}\n")
            f.write(f"has_tool_calls: {bool(msg.tool_calls)}\n")
            f.write(f"content: {(msg.content or '')[:200]}\n\n")

        tool_calls = None
        raw_tool_calls = None
        stop_reason = "end_turn"
        if msg.tool_calls:
            import json
            tool_calls = []
            raw_tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })
                # 保留 OpenAI 原始格式，构造 assistant 消息时需要
                raw_tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })
            stop_reason = "tool_use"

        return {
            "content": msg.content or "",
            "tool_calls": tool_calls,
            "stop_reason": stop_reason,
            "raw": response,
            "raw_tool_calls": raw_tool_calls,
        }


class MiMoClient(OpenAIClient):

    def _get_api_key(self) -> str:
        return settings.mimo_api_key

    def _get_base_url(self) -> str:
        return settings.mimo_api_base

    def _get_model(self) -> str:
        return settings.mimo_model


class DeepSeekClient(OpenAIClient):

    def _get_api_key(self) -> str:
        return settings.deepseek_api_key

    def _get_base_url(self) -> str:
        return "https://api.deepseek.com/v1"

    def _get_model(self) -> str:
        return settings.deepseek_model


class QwenClient(OpenAIClient):

    def _get_api_key(self) -> str:
        return settings.qwen_api_key

    def _get_base_url(self) -> str:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def _get_model(self) -> str:
        return settings.qwen_model


class AnthropicClient(BaseLLMClient):

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    def chat(self, messages: List[Dict], system: str = "",
             tools: List[Dict] = None) -> Dict:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        content_text = ""
        tool_calls = None
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        stop_reason = "tool_use" if tool_calls else "end_turn"

        return {
            "content": content_text,
            "tool_calls": tool_calls,
            "stop_reason": stop_reason,
            "raw": response,
        }
