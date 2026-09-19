"""微博渠道：热搜 + 博文正文（只读公开内容，不使用登录态）.

backend 现状（2026-09 实测，数据中心 IP 下）：
- 主站 ajax 接口与 m.weibo.cn 均存在 IP 层封锁可能（本沙箱为 TLS 层拒连）；
  住宅网络通常可用。多后端 + doctor 兜底。
- 评论接口 (comments/hotflow) 当前普遍要求登录态 → v0.1 不覆盖，doctor 标注.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ..errors import ChannelError
from ..http import DESKTOP_UA, MOBILE_UA, get, get_json
from ..output import strip_html, truncate

BID_RE = re.compile(r"weibo\.(?:com|cn)/(?:status/|\d+/)?([A-Za-z0-9]+)")
MID_RE = re.compile(r"/status/(\d+)")


def _parse_post_ref(text: str) -> str:
    """从 URL 或纯 ID 提取帖子标识（m.weibo.cn status 的 bid 或数字 id）."""
    text = text.strip()
    if re.fullmatch(r"[0-9]+", text):
        return text
    m = MID_RE.search(text)
    if m:
        return m.group(1)
    m = BID_RE.search(text)
    if m and len(m.group(1)) >= 8:  # bid 是较长的 base62
        return m.group(1)
    raise ValueError(f"无法从 {text!r} 解析微博帖子 ID")


# ---------------- 热搜 backends ----------------


def _parse_hot_ajax(data: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    realtime = ((data or {}).get("data") or {}).get("realtime") or []
    out = []
    for i, e in enumerate(realtime[:limit], 1):
        out.append(
            {
                "rank": e.get("rank") or i,
                "word": e.get("word", ""),
                "note": e.get("note", ""),
                "heat": e.get("num"),
                "label": e.get("label_name") or "",
                "url": f"https://s.weibo.com/weibo?q=%23{e.get('word', '')}%23",
            }
        )
    if not out:
        raise ValueError("empty realtime list")
    return out


def _hot_ajax(limit: int) -> list[dict[str, Any]]:
    data = get_json("https://weibo.com/ajax/side/hotSearch", ua=DESKTOP_UA)
    return _parse_hot_ajax(data, limit)


def _parse_hot_mobile(data: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    cards = ((data or {}).get("data") or {}).get("cards") or []
    out = []
    for group in cards:
        for e in group.get("card_group", []):
            scheme = e.get("scheme", "")
            word = e.get("desc", "")
            if not word:
                continue
            out.append(
                {
                    "rank": len(out) + 1,
                    "word": word,
                    "note": e.get("desc_extran", ""),
                    "heat": e.get("desc_extran") if e.get("desc_extran", "").isdigit() else None,
                    "label": "",
                    "url": scheme.replace("sinaweibo://", "https://m.weibo.cn/") or "",
                }
            )
            if len(out) >= limit:
                return out
    if not out:
        raise ValueError("empty mobile cards")
    return out


def _hot_mobile(limit: int) -> list[dict[str, Any]]:
    data = get_json(
        "https://m.weibo.cn/api/container/getIndex"
        "?containerid=106003type%3D25%26t%3D3%26relative%3D0%26st%3D0",
        ua=MOBILE_UA,
    )
    return _parse_hot_mobile(data, limit)


HOT_BACKENDS: list[tuple[str, Callable[[int], list[dict[str, Any]]]]] = [
    ("weibo.com/ajax/side/hotSearch", _hot_ajax),
    ("m.weibo.cn container 106003", _hot_mobile),
]


def hot_search(limit: int = 50) -> tuple[list[dict[str, Any]], str]:
    errors: list[str] = []
    for name, backend in HOT_BACKENDS:
        try:
            return backend(limit), name
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    raise ChannelError("weibo-hot", "所有热搜后端均失败(常见原因: 出口 IP 被封/TLS 拒连)", errors)


# ---------------- 博文 backends ----------------


def _post_mobile(ref: str) -> dict[str, Any]:
    if ref.isdigit():
        data = get_json(f"https://m.weibo.cn/statuses/show?id={ref}", ua=MOBILE_UA)
        if not isinstance(data, dict) or not data.get("ok"):
            raise ValueError(f"show failed: {str(data)[:120]}")
        d = data.get("data") or {}
    else:
        # bid 形态：先从 status 页面里抠出数字 id
        page = get(f"https://m.weibo.cn/status/{ref}", ua=MOBILE_UA)
        m = re.search(r'"id":\s*(\d{15,})', page.text)
        if not m:
            m2 = re.search(r"statuses/show\?id=(\d{15,})", page.text)
            if not m2:
                raise ValueError("cannot extract numeric id from status page")
            m = m2
        data = get_json(f"https://m.weibo.cn/statuses/show?id={m.group(1)}", ua=MOBILE_UA)
        if not isinstance(data, dict) or not data.get("ok"):
            raise ValueError(f"show failed: {str(data)[:120]}")
        d = data.get("data") or {}
    return _clean_post(d)


def _clean_post(d: dict[str, Any]) -> dict[str, Any]:
    long_text = ((d.get("longText") or {}).get("longTextContent")) or ""
    content = long_text or d.get("text", "")
    return {
        "author": (d.get("user") or {}).get("screen_name", "未知用户"),
        "author_desc": (d.get("user") or {}).get("description", ""),
        "created_at": d.get("created_at", ""),
        "content": truncate(strip_html(content), 3000),
        "reposts": d.get("reposts_count"),
        "comments": d.get("comments_count"),
        "likes": d.get("attitudes_count"),
        "url": d.get("scheme") or "",
        "source": (d.get("source") or "").strip("  "),
    }


POST_BACKENDS: list[tuple[str, Callable[[str], dict[str, Any]]]] = [
    ("m.weibo.cn/statuses/show", _post_mobile),
]


def post(ref: str) -> tuple[dict[str, Any], str]:
    errors: list[str] = []
    for name, backend in POST_BACKENDS:
        try:
            return backend(_parse_post_ref(ref)), name
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    raise ChannelError("weibo-post", "所有博文后端均失败(评论区接口需登录态, v0.1 不覆盖)", errors)


def hot_markdown(items: list[dict[str, Any]]) -> str:
    lines = ["| # | 话题 | 标签 | 热度 |", "|---|---|---|---|"]
    for it in items:
        lines.append(f"| {it['rank']} | {it['word']} | {it['label'] or '-'} | {it['heat'] or '-'} |")
    return "\n".join(lines)


def post_markdown(p: dict[str, Any]) -> str:
    parts = [
        f"## @{p['author']} 的微博",
        "",
        f"- 时间: {p['created_at']}  来源: {p['source'] or '-'}",
        f"- 转发 {p['reposts']} · 评论 {p['comments']} · 赞 {p['likes']}",
        "",
        p["content"],
    ]
    return "\n".join(parts).strip()


__all__ = ["HOT_BACKENDS", "POST_BACKENDS", "hot_markdown", "hot_search", "post", "post_markdown"]
