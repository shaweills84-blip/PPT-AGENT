import json
import re
from typing import Dict, Optional
from core.llm_client import get_llm_client
from agent.prompts import OUTLINE_AGENT_PROMPT, SELF_REFLECTION_PROMPT


class OutlineAgent:
    """大纲子 Agent,负责把研究素材组织成 PPT 结构，不负责找信息"""

    def __init__(self):
        self.client = get_llm_client()

    def plan(self, research_report: dict, user_prompt: str = "",
             template_style: str = "",
             enable_self_reflection: bool = True) -> dict:
        report_json = json.dumps(research_report, ensure_ascii=False, indent=2)

        style_hint = ""
        if template_style:
            style_hint = f"\n\n用户偏好的PPT风格：{template_style}"

        user_message = (
            f"【用户需求】{user_prompt}\n\n"
            f"【研究报告】\n{report_json}\n"
            f"{style_hint}\n\n"
            f"请基于研究报告规划完整的PPT结构。"
            f"确保每页的 bullet 使用研究报告中的真实内容，禁止使用占位符。"
        )

        response = self.client.chat(
            messages=[{"role": "user", "content": user_message}],
            system=OUTLINE_AGENT_PROMPT,
        )

        content = response["content"] or ""
        ppt = self._parse_slides(content)

        if not ppt:
            # 重试
            retry_msg = "请直接输出完整的PPT JSON结构。格式：{\"title\": \"...\", \"slides\": [...]}"
            response = self.client.chat(
                messages=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": retry_msg},
                ],
                system=OUTLINE_AGENT_PROMPT,
            )
            ppt = self._parse_slides(response["content"] or "")

        if enable_self_reflection and ppt:
            ppt = self._self_reflection(ppt, user_prompt, research_report)

        return ppt or self._empty_slides()

    def revise(self, current_slides: dict, feedback: str,
               research_report: dict = None) -> dict:
        slides_json = json.dumps(current_slides, ensure_ascii=False, indent=2)
        report_json = json.dumps(research_report or {}, ensure_ascii=False, indent=2)

        user_message = (
            f"【当前PPT大纲】\n{slides_json}\n\n"
            f"【修改意见】{feedback}\n\n"
            f"【原始研究报告（供参考）】\n{report_json}\n\n"
            f"请根据修改意见重新生成PPT大纲JSON。"
        )

        response = self.client.chat(
            messages=[{"role": "user", "content": user_message}],
            system=OUTLINE_AGENT_PROMPT,
        )

        ppt = self._parse_slides(response["content"] or "")
        return ppt or current_slides

    def _self_reflection(self, ppt: dict, user_prompt: str,
                         research_report: dict) -> dict:
        original = json.dumps(ppt, ensure_ascii=False, indent=2)
        message = (
            f"用户需求：{user_prompt}\n\n"
            f"研究报告：{json.dumps(research_report, ensure_ascii=False)}\n\n"
            f"PPT大纲：\n{original}\n\n"
            f"{SELF_REFLECTION_PROMPT}"
        )
        try:
            response = self.client.chat(
                messages=[{"role": "user", "content": message}],
                system=OUTLINE_AGENT_PROMPT,
            )
            refined = self._parse_slides(response["content"] or "")
            if refined:
                return refined
        except Exception:
            pass
        return ppt

    def _parse_slides(self, content: str) -> Optional[dict]:
        def _extract(result: dict) -> Optional[dict]:
            if "slides" in result:
                return result
            # LLM 有时包一层 presentation/ppt/outline
            for wrapper in ("presentation", "ppt", "outline"):
                if wrapper in result and isinstance(result[wrapper], dict):
                    inner = result[wrapper]
                    if "slides" in inner:
                        return inner
            return None

        try:
            result = json.loads(content)
            extracted = _extract(result)
            if extracted:
                return extracted
        except json.JSONDecodeError:
            pass

        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            try:
                extracted = _extract(json.loads(match.group(1)))
                if extracted:
                    return extracted
            except json.JSONDecodeError:
                pass

        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and start < end:
            try:
                extracted = _extract(json.loads(content[start:end + 1]))
                if extracted:
                    return extracted
            except json.JSONDecodeError:
                pass

        return None

    def _empty_slides(self) -> dict:
        return {
            "title": "未命名PPT",
            "slides": [
                {"type": "title", "title": "未命名PPT", "subtitle": ""},
                {"type": "summary", "title": "说明", "bullets": ["大纲生成失败，请重试。"]},
            ]
        }
