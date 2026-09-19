"""知乎渠道：热榜（稳定）+ 问答（尽力而为，受 IP 信誉影响）.

backend 现状（2026-09 实测）：
- 热榜: api.zhihu.com/topstory/hot-list ✅ / topstory/hot-lists/total ✅
       (www.zhihu.com/api/v3 同路径需要登录, 不采用)
- 问答: api.zhihu.com 与 www.zhihu.com/api/v4 的 answers 接口均可能触发
       40362 风控（IP 信誉相关）——住宅网络下通常可用, 数据中心 IP 常被拦.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ..errors import ChannelError
from ..http import get_json
from ..output import strip_html, truncate

QUESTION_URL_RE = re.compile(r"zhihu\.com/questions?/(\d+)")


def parse_question_id(text: str) -> int:
    """接受纯数字 ID 或任意形态的知乎问题链接."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    m = QUESTION_URL_RE.search(text)
    if m:
        return int(m.group(1))
    raise ValueError(f"无法从 {text!r} 解析知乎问题 ID")


def _clean_hot_item(entry: dict[str, Any]) -> dict[str, Any]:
    target = entry.get("target") or {}
    qid = target.get("id")
    # card_label 可能是标签 dict 列表 / 字符串 / dict——只提取可读的 text
    raw_labels = entry.get("card_label") or []
    if isinstance(raw_labels, str):
        tags = [raw_labels] if raw_labels else []
    elif isinstance(raw_labels, list):
        tags = [lbl["text"] for lbl in raw_labels if isinstance(lbl, dict) and lbl.get("text")]
    elif isinstance(raw_labels, dict):
        tags = [raw_labels["text"]] if raw_labels.get("text") else []
    else:
        tags = []
    return {
        "title": (target.get("title") or "").strip(),
        # 统一给人/agent 可用的 www 链接；仅在无 id 时退回原 url
        "url": f"https://www.zhihu.com/question/{qid}" if qid else (target.get("url") or ""),
        "excerpt": truncate(strip_html(target.get("excerpt") or ""), 120),
        "answer_count": target.get("answer_count"),
        "follower_count": target.get("follower_count"),
        "heat": (entry.get("detail_text") or "").strip(),
        "tags": tags,
    }


# ---------------- 热榜 backends ----------------


def _hot_v4(limit: int) -> list[dict[str, Any]]:
    data = get_json(
        f"https://api.zhihu.com/topstory/hot-list?limit={limit}",
        headers={"Referer": "https://api.zhihu.com/"},
    )
    if not isinstance(data, dict) or "data" not in data:
        raise ValueError(f"unexpected payload: {str(data)[:120]}")
    return [_clean_hot_item(e) for e in data["data"][:limit] if e.get("target")]


def _hot_v3(limit: int) -> list[dict[str, Any]]:
    data = get_json(f"https://api.zhihu.com/topstory/hot-lists/total?limit={limit}")
    if not isinstance(data, dict) or "data" not in data:
        raise ValueError(f"unexpected payload: {str(data)[:120]}")
    return [_clean_hot_item(e) for e in data["data"][:limit] if e.get("target")]


HOT_BACKENDS: list[tuple[str, Callable[[int], list[dict[str, Any]]]]] = [
    ("api.zhihu.com/topstory/hot-list", _hot_v4),
    ("api.zhihu.com/topstory/hot-lists/total", _hot_v3),
]


def hot_list(limit: int = 50) -> tuple[list[dict[str, Any]], str]:
    """返回 (热榜条目, 命中的 backend 名)."""
    errors: list[str] = []
    for name, backend in HOT_BACKENDS:
        try:
            return backend(limit), name
        except Exception as e:  # noqa: BLE001 — 逐个后端降级
            errors.append(f"{name}: {e}")
    raise ChannelError("zhihu-hot", "所有热榜后端均失败", errors)


# ---------------- 问答 backends（尽力而为） ----------------


def _question_detail_api(qid: int) -> dict[str, Any]:
    data = get_json(f"https://api.zhihu.com/questions/{qid}")
    if not isinstance(data, dict) or "error" in data or "id" not in data:
        err = (data or {}).get("error", {}) if isinstance(data, dict) else {}
        raise ValueError(f"risk-control {err.get('code')}: {err.get('message', '')[:80]}")
    return {
        "id": qid,
        "title": data.get("title", ""),
        "detail": truncate(strip_html(data.get("detail") or ""), 600),
        "answer_count": data.get("answer_count"),
        "follower_count": data.get("follower_count"),
        "url": f"https://www.zhihu.com/question/{qid}",
    }


def _answers_api(qid: int, limit: int) -> list[dict[str, Any]]:
    data = get_json(
        f"https://api.zhihu.com/questions/{qid}/answers?offset=0&limit={limit}"
        "&include=voteup_count,comment_count"
    )
    if not isinstance(data, dict) or "data" not in data:
        err = (data or {}).get("error", {}) if isinstance(data, dict) else {}
        raise ValueError(f"risk-control {err.get('code')}: {err.get('message', '')[:80]}")
    out = []
    for a in data.get("data", [])[:limit]:
        author = (a.get("author") or {}).get("name", "匿名用户")
        out.append(
            {
                "author": author,
                "voteup": a.get("voteup_count"),
                "comment_count": a.get("comment_count"),
                "content": truncate(strip_html(a.get("content") or ""), 2000),
                "url": a.get("url") or f"https://www.zhihu.com/question/{qid}/answer/{a.get('id', '')}",
            }
        )
    if not out:
        raise ValueError("empty answer list")
    return out


def _answers_v4(qid: int, limit: int) -> list[dict[str, Any]]:
    data = get_json(
        f"https://www.zhihu.com/api/v4/questions/{qid}/answers?offset=0&limit={limit}"
        "&include=voteup_count,comment_count",
        headers={"Referer": f"https://www.zhihu.com/question/{qid}"},
    )
    if not isinstance(data, dict) or "data" not in data:
        err = (data or {}).get("error", {}) if isinstance(data, dict) else {}
        raise ValueError(f"risk-control {err.get('code')}: {err.get('message', '')[:80]}")
    out = []
    for a in data.get("data", [])[:limit]:
        author = (a.get("author") or {}).get("name", "匿名用户")
        out.append(
            {
                "author": author,
                "voteup": a.get("voteup_count"),
                "comment_count": a.get("comment_count"),
                "content": truncate(strip_html(a.get("content") or ""), 2000),
                "url": a.get("url") or f"https://www.zhihu.com/question/{qid}/answer/{a.get('id', '')}",
            }
        )
    if not out:
        raise ValueError("empty answer list")
    return out


def _answers_jina(qid: int, limit: int) -> list[dict[str, Any]]:
    """r.jina.ai 中继：数据中心 IP 被风控时的兜底路线（国内/住宅网络通常可用）."""
    from ..http import get

    resp = get(f"https://r.jina.ai/https://www.zhihu.com/question/{qid}", timeout=30.0)
    if resp.status_code != 200:
        raise ValueError(f"jina relay HTTP {resp.status_code}")
    md = resp.text
    # 回答以 answer 链接为界切片
    marks = [
        (m.start(), m.group(1))
        for m in re.finditer(rf"zhihu\.com/question/{qid}/answer/(\d+)", md)
    ]
    if not marks:
        raise ValueError("no answer links in relay output")
    out = []
    for idx, (pos, aid) in enumerate(marks[:limit]):
        seg = md[pos : marks[idx + 1][0] if idx + 1 < len(marks) else len(md)]
        seg_text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", seg)  # 去链接语法
        vm = re.search(r"([\d,.]+)\s*万?\s*人?\s*赞同", seg_text)
        voteup = 0
        if vm:
            v = vm.group(1).replace(",", "")
            voteup = int(float(v) * 10000) if "万" in vm.group(0) else int(float(v))
        content = truncate(strip_html(seg_text), 2000)
        if len(content) < 30:
            continue
        out.append(
            {
                "author": "未知用户",
                "voteup": voteup,
                "comment_count": None,
                "content": content,
                "url": f"https://www.zhihu.com/question/{qid}/answer/{aid}",
            }
        )
    if not out:
        raise ValueError("relay produced no usable answers")
    return out


ANSWER_BACKENDS: list[tuple[str, Callable[[int, int], list[dict[str, Any]]]]] = [
    ("api.zhihu.com/questions/{id}/answers", _answers_api),
    ("www.zhihu.com/api/v4/questions/{id}/answers", _answers_v4),
    ("r.jina.ai 中继", _answers_jina),
]


def question(
    qid: int, max_answers: int = 5
) -> tuple[dict[str, Any], list[dict[str, Any]], str, str | None]:
    """返回 (问题详情或None, 回答列表, 回答backend, 备注)."""
    detail: dict[str, Any] | None = None
    note: str | None = None
    try:
        detail = _question_detail_api(qid)
    except Exception as e:  # noqa: BLE001
        note = f"问题详情接口被风控({str(e)[:60]})，仅返回回答"
        detail = {
            "id": qid,
            "title": f"知乎问题 {qid}",
            "detail": "",
            "answer_count": None,
            "follower_count": None,
            "url": f"https://www.zhihu.com/question/{qid}",
        }

    errors: list[str] = []
    for name, backend in ANSWER_BACKENDS:
        try:
            answers = backend(qid, max_answers)
            return detail, answers, name, note
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    raise ChannelError("zhihu-question", "所有问答后端均被拦截(多为 IP 信誉风控)", errors)


def hot_markdown(items: list[dict[str, Any]]) -> str:
    lines = ["| # | 话题 | 热度 | 回答数 |", "|---|---|---|---|"]
    for i, it in enumerate(items, 1):
        tags = "/".join(it["tags"]) or ""
        title = f"{it['title']} {tags}".strip()
        lines.append(f"| {i} | [{title}]({it['url']}) | {it['heat']} | {it['answer_count'] or '-'} |")
    return "\n".join(lines)


def question_markdown(detail: dict[str, Any], answers: list[dict[str, Any]]) -> str:
    parts = [f"## {detail['title']}", "", f"链接: {detail['url']}", ""]
    if detail.get("detail"):
        parts += [detail["detail"], ""]
    if detail.get("answer_count") is not None:
        parts += [f"共 {detail['answer_count']} 个回答", ""]
    for i, a in enumerate(answers, 1):
        parts += [
            f"### 回答 {i} — {a['author']}（赞 {a['voteup']}）",
            "",
            a["content"],
            "",
            f"来源: {a['url']}",
            "",
        ]
    return "\n".join(parts).strip()


__all__ = [
    "ANSWER_BACKENDS",
    "HOT_BACKENDS",
    "hot_list",
    "hot_markdown",
    "parse_question_id",
    "question",
    "question_markdown",
]
