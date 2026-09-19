"""HTTP 底座：UA 池、超时、轻量重试、代理透传.

多后端路由的语义由各 channel 自己实现（每个 backend 一个纯函数，
按顺序尝试，拿到可解析数据才算成功）——这里只提供单次请求原语.
"""

from __future__ import annotations

import httpx

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

DEFAULT_TIMEOUT = 10.0


def get(
    url: str,
    *,
    ua: str = DESKTOP_UA,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Response:
    """GET with browser-like headers; raises httpx errors on transport failure."""
    base = {
        "User-Agent": ua,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    if headers:
        base.update(headers)
    # trust_env=True: 透传 HTTP(S)_PROXY / ZHIWEI_PROXY 类环境变量
    with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
        return client.get(url, headers=base)


def get_json(url: str, **kwargs) -> object:
    """GET and parse JSON, raising a readable error on bad payloads."""
    resp = get(url, **kwargs)
    try:
        return resp.json()
    except ValueError as e:
        raise ValueError(f"non-JSON response from {url} (HTTP {resp.status_code}): {e}") from e
