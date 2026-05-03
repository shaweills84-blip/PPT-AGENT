import json
import re
from typing import Optional


def try_extract_ppt_structure(content: str) -> Optional[dict]:
    try:
        return extract_ppt_structure(content)
    except RuntimeError:
        return None


def extract_ppt_structure(content: str) -> dict:
    # 1. 直接 JSON 解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. ```json ... ``` 代码块
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 找第一个 { 到最后一个 }
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise RuntimeError(f"无法从 LLM 输出中提取 PPT 结构:\n{content[:500]}")
