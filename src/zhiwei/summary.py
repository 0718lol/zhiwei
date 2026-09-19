"""公众号文章 TextRank 摘要 —— 深度层第二个引擎（确定性、无 LLM）.

抽取式摘要：句子图 + TextRank 权重迭代，取 top-N 按原文顺序输出；
同时抽取关键数据点（百分比/金额/倍数）——行业深度文最值钱的是数字.
"""

from __future__ import annotations

import re
from collections import Counter

_STOP2 = {
    "的话", "一个", "什么", "没有", "就是", "但是", "所以", "因为", "如果", "这个", "那个",
    "我们", "自己", "可以", "这种", "还是", "只是", "而且", "然后", "不过", "这些", "时候",
    "现在", "已经", "这样", "一下", "很多", "非常", "真的", "可能", "其实", "问题", "对于",
}
_NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|亿|万|千|倍|美元|元|人|年)")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?\n]+", text or "")
    return [p.strip() for p in parts if 15 <= len(p.strip()) <= 300]


def _grams(s: str) -> set[str]:
    clean = re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9]+", "", s)
    grams = {clean[i : i + 2] for i in range(len(clean) - 1)} - _STOP2
    words = set(re.findall(r"[a-zA-Z]{2,}|\d+", clean))
    return grams | words


def _textrank(sentences: list[str], iters: int = 30, d: float = 0.85) -> list[float]:
    n = len(sentences)
    if n == 0:
        return []
    grams = [_grams(s) for s in sentences]
    sim: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            union = grams[i] | grams[j]
            s = len(grams[i] & grams[j]) / len(union) if union else 0.0
            sim[i][j] = sim[j][i] = s
    out_sum = [sum(row) or 1.0 for row in sim]
    rank = [1.0 / n] * n
    for _ in range(iters):
        new = [1.0 - d] * n
        for i in range(n):
            for j in range(n):
                if sim[j][i]:
                    new[i] += d * rank[j] * sim[j][i] / out_sum[j]
        rank = new
    return rank


def key_numbers(text: str, top: int = 6) -> list[str]:
    hits = _NUM_RE.findall(text or "")
    counter = Counter(h.strip() for h in hits)
    return [k for k, _ in counter.most_common(top)]


def summarize(text: str, n: int = 5) -> dict:
    """返回 {sentences(原文顺序), numbers}；text 为纯文本/轻 markdown."""
    sents = _sentences(text)
    if not sents:
        return {"sentences": [], "numbers": key_numbers(text)}
    rank = _textrank(sents)
    order = sorted(range(len(sents)), key=lambda i: rank[i], reverse=True)[: max(1, n)]
    chosen = sorted(order)  # 恢复原文顺序
    return {
        "sentences": [sents[i] for i in chosen],
        "numbers": key_numbers(text),
    }


def summary_markdown(title: str, meta_line: str, s: dict) -> str:
    lines = [f"# {title}", "", meta_line, "", "## 摘要（TextRank 抽取）", ""]
    lines += [f"- {s_}" for s_ in s["sentences"]] or ["（正文太短，无可抽取句子）"]
    if s["numbers"]:
        lines += ["", "## 关键数据点", "", "· " + "  ".join(s["numbers"])]
    lines += ["", "---", "*方法：TextRank 抽取式摘要 + 数字模式抽取，无 LLM*"]
    return "\n".join(lines)
