"""输出层：一切输出都为 LLM 消费优化 —— 干净 markdown、可控截断、可选 JSON."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

_TAG_RE = re.compile(r"<[^>]+>")


_BLOCK_TAG_RE = re.compile(
    r"(?i)</?(?:p|div|br|li|tr|h[1-6]|blockquote|section|article|figcaption)[^>]*>"
)


def strip_html(html: str) -> str:
    """HTML → plain text：块级标签转换行，行内标签就地展开（不破坏词句）."""
    if not html:
        return ""
    html = _BLOCK_TAG_RE.sub("\n", html)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text()
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + f"…(已截断, 原文 {len(text)} 字)"


def html_to_markdown(html: str) -> str:
    """公众号正文等富内容 → markdown（html2text，链接图片保留）."""
    if not html:
        return ""
    import html2text  # 延迟导入：非正文场景不付出解析成本

    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_images = False
    h.ignore_emphasis = False
    h.skip_internal_links = True
    md = h.handle(html)
    # 压缩 3+ 连续空行
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def meta(source_url: str, backend: str) -> dict:
    """每条输出的元信息块：来源、走的后端、抓取时间（UTC+8 由调用方本地时区呈现）."""
    return {
        "source": source_url,
        "backend": backend,
        "fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


def render(header: str, sections: list[str], data: object = None, as_json: bool = False) -> str:
    """统一渲染：默认 markdown（标题 + 分节），--json 时输出结构化数据."""
    if as_json:
        return json.dumps(data, ensure_ascii=False, indent=2)
    parts = [f"# {header}", ""]
    parts += [s for s in sections if s]
    return "\n".join(parts).strip()


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """小表格渲染（doctor / 热榜摘要用）."""
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join("---" for _ in headers) + "|"
    body = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])
