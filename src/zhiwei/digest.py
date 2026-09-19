"""观点聚合引擎 —— 知微"深度层"的心脏（v0.1：确定性规则，无 LLM 依赖）.

输入一组回答（作者/赞数/正文/链接），输出结构化的观点图谱：
- 立场聚类：支持 / 反对(质疑) / 事实中立 三阵营，按条数与赞数双口径占比
- 每阵营代表观点：赞数最高的 2 条，抽取核心观点句（立场词/数字/位置加权）
- 高频关键词：中文 2-gram 词频（停用词过滤），勾勒讨论焦点

设计立场：这是给"调用方 agent"的半成品——确定性的部分我们做完做扎实，
主观综合留给 agent。输出永远自带方法说明，不冒充 LLM 级洞察。
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# 立场词表（v0.1 规则引擎；可随真实语料迭代）
_SUPPORT = [
    "支持", "赞同", "同意", "赞成", "正确", "没错", "确实是", "确实是", "看好", "厉害",
    "优秀", "值得", "应该", "必然", "一定会", "利好了", "称赞", "认可", "有道理", "说到点子",
]
_OPPOSE = [
    "反对", "不认同", "不同意", "不赞成", "质疑", "荒谬", "扯淡", "误导", "错误", "不可能",
    "恰恰相反", "根本不", "并不是", "别信", "骗局", "讽刺", "过誉", "名不副实", "利空",
    "问题在于", "糟糕", "失望", "相反", "恰恰", "未必", "不见得", "清醒一点", "割韭菜",
]
_FACT = [
    "数据", "统计", "根据", "来源", "据报道", "调查显示", "比例", "增长", "下降", "截至",
    "历史上", "事实上", "公开资料", "财报", "年报", "论文", "研究", "同比增长", "环比",
]

_SENT_SPLIT = re.compile(r"[。！？!?\n]+")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|亿|万|千|倍|年|人|次|元|美元|块钱)")
# 中文 2-gram 停用成分：常见虚词组合与标点
_STOP2 = {
    "的话", "一个", "什么", "没有", "就是", "但是", "可是", "所以", "因为", "如果", "这个",
    "那个", "他们", "我们", "你们", "自己", "可以", "这种", "那种", "还是", "只是", "而且",
    "然后", "不过", "这些", "那些", "问题", "回答", "感觉", "觉得", "时候", "现在", "出来",
    "开始", "已经", "这样", "那样", "一下", "一些", "很多", "非常", "真的", "不知道",
}


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if 8 <= len(s.strip()) <= 200]


def _stance_scores(text: str) -> dict[str, int]:
    return {
        "支持": sum(1 for w in _SUPPORT if w in text),
        "反对": sum(1 for w in _OPPOSE if w in text),
        "事实": sum(1 for w in _FACT if w in text),
    }


def _classify(text: str) -> str:
    scores = _stance_scores(text)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "未知"


def _core_sentence(text: str, stance: str) -> str:
    """抽取最能代表该回答立场的句子：立场词 + 数字 + 靠前位置加权."""
    sentences = _split_sentences(text)
    if not sentences:
        return (text or "").strip()[:120]
    best, best_score = sentences[0], -1.0
    for i, s in enumerate(sentences[:10]):
        score = _stance_scores(s)[stance] * 2.0
        if _NUM_RE.search(s):
            score += 1.0
        if i < 3:
            score += 1.0
        if 20 <= len(s) <= 120:
            score += 0.5
        if score > best_score:
            best, best_score = s, score
    return best


def _keywords(texts: list[str], top: int = 8) -> list[tuple[str, int]]:
    """2-gram 关键词：要求出现在 ≥2 个不同文本中（文档频率），过滤单文噪音."""
    df: Counter[str] = Counter()
    for t in texts:
        clean = re.sub(r"[^\u4e00-\u9fff]+", " ", t)
        grams = {
            g
            for g in re.findall(r"[\u4e00-\u9fff]{2}", clean)
            if g not in _STOP2
        }
        df.update(grams)
    # 文档频率 >= 2 才算"讨论焦点"，按出现文本数排序
    common = [(g, n) for g, n in df.items() if n >= 2]
    common.sort(key=lambda x: (-x[1], x[0]))
    return common[:top]


def digest(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """answers: [{author, voteup, content, url}, ...] → 观点聚合结构."""
    items = []
    for a in answers:
        content = a.get("content") or ""
        if not content.strip():
            continue
        stance = _classify(content)
        items.append(
            {
                "author": a.get("author") or "匿名用户",
                "voteup": int(a.get("voteup") or 0),
                "url": a.get("url") or "",
                "stance": stance,
                "core": _core_sentence(content, stance),
            }
        )
    items.sort(key=lambda x: x["voteup"], reverse=True)

    total = len(items)
    total_votes = sum(i["voteup"] for i in items) or 1
    camps: dict[str, list[dict[str, Any]]] = {"支持": [], "反对": [], "事实": [], "未知": []}
    for it in items:
        camps[it["stance"]].append(it)

    camp_stats = {}
    for name, members in camps.items():
        if not members:
            camp_stats[name] = {"count": 0, "count_pct": 0, "vote_pct": 0, "representatives": []}
            continue
        camp_stats[name] = {
            "count": len(members),
            "count_pct": round(len(members) * 100 / total, 1),
            "vote_pct": round(sum(m["voteup"] for m in members) * 100 / total_votes, 1),
            # 代表观点：赞数最高的 2 条
            "representatives": members[:2],
        }

    kw = _keywords([a.get("content", "") for a in answers])
    return {
        "total_answers": total,
        "total_votes": total_votes,
        "camps": camp_stats,
        "keywords": kw,
        "method": "确定性规则引擎(立场词表+核心句加权)，无 LLM；供调用方 agent 综合判断",
    }


def digest_markdown(question_title: str, d: dict[str, Any]) -> str:
    lines = []
    lines += [
        f"共聚合 {d['total_answers']} 个回答、{d['total_votes']} 赞。"
        f"焦点关键词：{'、'.join(f'{w}({n})' for w, n in d['keywords'])}",
        "",
    ]
    label = {"支持": "👍 支持方", "反对": "👎 反对方(质疑)", "事实": "📊 事实/中立", "未知": "❔ 立场不明"}
    for name in ["支持", "反对", "事实", "未知"]:
        c = d["camps"][name]
        if c["count"] == 0:
            continue
        lines.append(
            f"## {label[name]} — {c['count']} 条（条数 {c['count_pct']}% · 赞数 {c['vote_pct']}%）"
        )
        for r in c["representatives"]:
            lines += ["", f"> **{r['author']}**（{r['voteup']} 赞）：{r['core']}", ""]
            if r["url"]:
                lines += [f"> 来源：{r['url']}", ""]
        lines.append("")
    lines += ["---", f"*方法：{d['method']}*"]
    return "\n".join(lines).strip()


def llm_enhance(question_title: str, d: dict[str, Any]) -> tuple[str | None, str]:
    """可选 LLM 增强：用 ZHIWEI_LLM_* 环境变量指定的 OpenAI 兼容端点，
    对确定性聚合结果做阵营命名、分歧提炼与总结.

    任何失败都安全降级为 (None, 原因)——确定性输出永远不受影响.
    返回 (增强文本, 说明).
    """
    import os

    base = os.environ.get("ZHIWEI_LLM_BASE_URL")
    key = os.environ.get("ZHIWEI_LLM_API_KEY")
    model = os.environ.get("ZHIWEI_LLM_MODEL")
    if not (base and key and model):
        return None, (
            "未配置 LLM（需 ZHIWEI_LLM_BASE_URL / ZHIWEI_LLM_API_KEY / ZHIWEI_LLM_MODEL "
            "环境变量），保持确定性输出"
        )

    camps = []
    for name in ("支持", "反对", "事实"):
        c = d["camps"][name]
        if c["count"]:
            reps = "；".join(
                f"{r['author']}({r['voteup']}赞)：{r['core'][:80]}" for r in c["representatives"]
            )
            camps.append(f"- {name} {c['count']} 条 / 赞数占 {c['vote_pct']}%：{reps}")
    kws = "、".join(w for w, _ in d["keywords"])
    prompt = (
        "以下是某知乎问题下高赞回答的确定性观点聚合结果（规则引擎产出）。请用中文：\n"
        "1. 给每个阵营一个更精准的命名（如「支持方」→「支持派：政策红利论」）；\n"
        "2. 提炼各阵营的核心分歧点（≤3 条）；\n"
        "3. 用两句话总结舆论场。\n"
        "严格基于所给信息，不要编造。\n\n"
        f"问题：{question_title}\n焦点关键词：{kws}\n" + "\n".join(camps)
    )
    try:
        import httpx

        resp = httpx.post(
            base.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        if not text:
            raise ValueError("empty completion")
        return text, f"LLM 增强成功（{model}）"
    except Exception as e:  # noqa: BLE001 — 降级是设计行为
        return None, f"LLM 增强失败({type(e).__name__}: {str(e)[:60]})，保持确定性输出"
