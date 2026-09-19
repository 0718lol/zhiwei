"""微信公众号渠道：单篇文章解析（v0.1 范围：给 URL 出干净 markdown）.

公众号没有稳定的公开发现入口（搜索需登录/验证码），发现类能力在 v0.2。
单篇文章 URL 通常无需登录即可读取。也接受本地 HTML 文件路径（离线解析，供测试）.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ..errors import ChannelError
from ..http import DESKTOP_UA, get
from ..output import html_to_markdown

URL_RE = re.compile(r"(https?://mp\.weixin\.qq\.com/s[?/\S]*)")


def _parse_ref(text: str) -> str:
    """接受完整 URL 或本地 HTML 文件路径."""
    text = text.strip()
    m = URL_RE.search(text)
    if m:
        return m.group(1)
    if Path(text).is_file():
        return text
    raise ValueError(f"不是有效的公众号文章 URL 或本地文件: {text[:80]!r}")


def _extract(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    if not title:
        h1 = soup.find("h1", id="activity-name")
        if h1:
            title = h1.get_text(strip=True)

    account = ""
    og_author = soup.find("meta", property="og:article:author")
    if og_author and og_author.get("content"):
        account = og_author["content"].strip()
    if not account:
        js_name = soup.find("a", id="js_name") or soup.find("span", id="js_name")
        if js_name:
            account = js_name.get_text(strip=True)

    publish_time = ""
    pt = soup.find("em", id="publish_time")
    if pt:
        publish_time = pt.get_text(strip=True)
    else:
        m = re.search(r'publish_time["\']?\s*[:=]\s*["\']([^"\']+)', html)
        if m:
            publish_time = m.group(1)

    body = soup.find("div", id="js_content") or soup.find("div", class_="rich_media_content")
    if not body:
        # 常见于“环境异常/需要验证”页
        if "环境异常" in html or "verify" in (title or "").lower():
            raise ValueError("微信返回验证页(环境异常)，本 IP 暂被风控")
        raise ValueError("未找到正文节点 js_content（可能被风控或链接失效）")

    for tag in body(["script", "style"]):
        tag.decompose()
    content_md = html_to_markdown(str(body))
    if len(content_md) < 20:
        raise ValueError("正文过短，疑似被风控页面")

    return {
        "title": title or "(无标题)",
        "account": account or "(未知公众号)",
        "publish_time": publish_time,
        "content": content_md,
        "url": source_url,
    }


def article(ref: str) -> tuple[dict[str, Any], str]:
    """返回 (文章数据, backend 名). ref 可以是 URL 或本地 HTML 路径."""
    ref = _parse_ref(ref)
    if not ref.startswith("http"):
        html = Path(ref).read_text(encoding="utf-8", errors="replace")
        try:
            return _extract(html, ref), "local-file"
        except ValueError as e:
            raise ChannelError("wechat-article", str(e)) from e
    try:
        resp = get(ref, ua=DESKTOP_UA, timeout=15.0)
    except Exception as e:  # noqa: BLE001
        raise ChannelError("wechat-article", f"请求失败: {e}") from e
    if resp.status_code != 200:
        raise ChannelError("wechat-article", f"HTTP {resp.status_code}（链接可能已失效）")
    try:
        return _extract(resp.text, ref), "mp.weixin.qq.com"
    except ValueError as e:
        raise ChannelError("wechat-article", str(e)) from e


def article_markdown(a: dict[str, Any]) -> str:
    parts = [
        f"## {a['title']}",
        "",
        f"- 公众号: {a['account']}",
        f"- 发布时间: {a['publish_time'] or '未知'}",
        "",
        a["content"],
    ]
    return "\n".join(parts).strip()


__all__ = ["article", "article_markdown"]
