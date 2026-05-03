from typing import List, Tuple


def rerank(query: str, chunks: List[str],
           strategy: str = "llm_rerank",
           top_k: int = 5) -> List[str]:
    if not chunks:
        return []
    if len(chunks) <= top_k:
        return chunks

    if strategy == "llm_rerank":
        return _llm_rerank(query, chunks, top_k)
    elif strategy == "diversity":
        return _diversity_rerank(chunks, top_k)
    else:
        return chunks[:top_k]


def _llm_rerank(query: str, chunks: List[str], top_k: int) -> List[str]:
    """用 LLM 对每个 chunk 打分（1-5），然后按分数重排"""
    try:
        from core.llm_client import get_llm_client
        client = get_llm_client()

        scored = []
        for i, chunk in enumerate(chunks):
            truncated = chunk[:800] if len(chunk) > 800 else chunk
            try:
                response = client.chat(
                    messages=[{
                        "role": "user",
                        "content": (
                            f"查询：{query}\n\n"
                            f"文档片段：\n{truncated}\n\n"
                            f"请评估这个文档片段与查询的相关程度，只输出1-5的数字。\n"
                            f"5=高度相关(直接回答问题)，4=相关，3=部分相关，2=微弱相关，1=不相关。"
                        ),
                    }],
                    system="你是一个检索结果评估器。只输出1-5的数字。",
                )
                score_text = (response.get("content") or "3").strip()
                score = int(''.join(c for c in score_text if c.isdigit()) or "3")
                score = max(1, min(5, score))
            except Exception:
                score = 3
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    except Exception:
        return chunks[:top_k]


def _diversity_rerank(chunks: List[str], top_k: int) -> List[str]:
    """贪心多样重排：每次选和已选结果最不相似的 chunk"""
    if len(chunks) <= top_k:
        return chunks

    selected = [chunks[0]]
    remaining = chunks[1:]

    while len(selected) < top_k and remaining:
        best_idx = 0
        best_score = -1
        for i, chunk in enumerate(remaining):
            min_similarity = min(
                _jaccard_similarity(chunk, sel) for sel in selected
            )
            if min_similarity < best_score or best_score == -1:
                best_score = min_similarity
                best_idx = i

        selected.append(remaining.pop(best_idx))

    return selected


def _jaccard_similarity(a: str, b: str) -> float:
    def bigrams(s):
        s = s[:500]
        return set(s[i:i+2] for i in range(len(s)-1))

    set_a, set_b = bigrams(a), bigrams(b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def rerank_with_scores(query: str, chunks: List[str],
                       strategy: str = "llm_rerank",
                       top_k: int = 5) -> List[Tuple[str, float]]:
    if not chunks:
        return []

    if strategy == "llm_rerank":
        import re
        try:
            from core.llm_client import get_llm_client
            client = get_llm_client()
            scored = []
            for chunk in chunks:
                truncated = chunk[:800] if len(chunk) > 800 else chunk
                try:
                    response = client.chat(
                        messages=[{
                            "role": "user",
                            "content": (
                                f"查询：{query}\n\n文档片段：\n{truncated}\n\n"
                                f"请评估相关性，只输出1-5的数字。"
                            ),
                        }],
                        system="你是一个检索结果评估器。只输出1-5的数字。",
                    )
                    score_text = (response.get("content") or "3").strip()
                    nums = re.findall(r'\d+', score_text)
                    score = float(nums[0]) if nums else 3.0
                except Exception:
                    score = 3.0
                scored.append((chunk, min(5.0, max(1.0, score))))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]
        except Exception:
            return [(c, 0.0) for c in chunks[:top_k]]

    return [(c, 0.0) for c in chunks[:top_k]]
