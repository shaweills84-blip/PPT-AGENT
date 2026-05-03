from typing import List


def rewrite_query(query: str, strategy: str = "llm") -> str:
    if strategy == "llm":
        return _llm_rewrite(query)
    elif strategy == "keyword":
        return _keyword_extract(query)
    elif strategy == "multi":
        queries = _multi_angle_rewrite(query)
        return "; ".join(queries)
    else:
        return query


def _llm_rewrite(query: str) -> str:
    try:
        from core.llm_client import get_llm_client
        client = get_llm_client()
        response = client.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"你是一个搜索查询优化器。将以下用户问题改写为2-3个适合文档检索的查询短语。\n\n"
                    f"规则：\n"
                    f"1. 提取核心实体和关系，去除口语化表达\n"
                    f"2. 使用关键词组合，而非完整句子\n"
                    f"3. 从不同角度覆盖用户意图\n"
                    f"4. 用分号(;)分隔多个查询\n"
                    f"5. 只输出查询短语，不要加任何解释\n\n"
                    f"用户问题：{query}\n\n"
                    f"查询短语："
                ),
            }],
            system="你是一个搜索查询优化器。只输出查询短语，不要解释。"
        )
        rewritten = (response.get("content") or "").strip()
        if rewritten:
            return rewritten
    except Exception:
        pass
    return query


def _keyword_extract(query: str) -> str:
    """不依赖 LLM 的轻量级提取"""
    import re
    stop_patterns = [
        r'帮我', r'能不能', r'可以', r'请', r'麻烦', r'我想', r'我要',
        r'看看', r'查一下', r'搜一下', r'找一下', r'这个', r'那个',
        r'怎么样', r'如何', r'怎么', r'什么', r'吗', r'呢', r'吧', r'啊',
    ]
    cleaned = query
    for pattern in stop_patterns:
        cleaned = re.sub(pattern, '', cleaned)

    words = re.findall(r'[一-鿿]{2,4}', cleaned)
    eng_words = re.findall(r'[a-zA-Z]{2,}', cleaned)

    result = ' '.join(words[:5] + eng_words)
    return result.strip() or query


def _multi_angle_rewrite(query: str) -> List[str]:
    try:
        from core.llm_client import get_llm_client
        client = get_llm_client()
        response = client.chat(
            messages=[{
                "role": "user",
                "content": (
                    f"从以下3个角度为给定问题生成检索查询：\n"
                    f"1. 直接检索：提取问题中的核心实体\n"
                    f"2. 扩展检索：覆盖问题相关的背景信息\n"
                    f"3. 数据检索：如果涉及数据，提取可量化的指标\n\n"
                    f"每个角度输出一行，用分号(;)分隔。不要加编号和解释。\n\n"
                    f"问题：{query}"
                ),
            }],
            system="你是一个搜索查询优化器。只输出查询短语。"
        )
        content = (response.get("content") or "").strip()
        if content:
            return [q.strip() for q in content.replace('\n', ';').split(';') if q.strip()]
    except Exception:
        pass
    return [query]


def rewrite_and_retrieve(query: str, document_id: int,
                         retriever, top_k: int = 5) -> List[str]:
    """改写 → 多路检索 → 合并去重"""
    queries = _multi_angle_rewrite(query)
    if len(queries) == 1:
        return retriever.retrieve(queries[0], document_id, top_k)

    seen = set()
    merged = []
    for q in queries:
        results = retriever.retrieve(q, document_id, top_k=3)
        for r in results:
            fingerprint = r[:100].strip()
            if fingerprint not in seen:
                seen.add(fingerprint)
                merged.append(r)

    return merged[:top_k]
