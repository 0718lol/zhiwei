"""doctor —— 一条命令报告每个渠道每个后端的真实状态.

设计原则（借鉴 Agent-Reach）：反爬世界里"坏了"是常态，诚实报告比假装可用重要.
"""

from __future__ import annotations

import time
from typing import Any

from .channels import weibo, zhihu
from .errors import ZhiweiError
from .http import DESKTOP_UA, get

_CHECKS: list[tuple[str, str, Any]] = [
    ("zhihu", "api.zhihu.com/topstory/hot-list", lambda: zhihu._hot_v4(3)),
    ("zhihu", "api.zhihu.com/topstory/hot-lists/total", lambda: zhihu._hot_v3(3)),
    ("zhihu", "api.zhihu.com/questions/{id}/answers", lambda: zhihu._answers_api(639662261, 2)),
    ("zhihu", "www.zhihu.com/api/v4/questions/{id}/answers", lambda: zhihu._answers_v4(639662261, 2)),
    ("weibo", "weibo.com/ajax/side/hotSearch", lambda: weibo._hot_ajax(3)),
    ("weibo", "m.weibo.cn container 106003", lambda: weibo._hot_mobile(3)),
    ("wechat", "mp.weixin.qq.com 可达性", lambda: get("https://mp.weixin.qq.com/", ua=DESKTOP_UA)),
]


def check_all() -> list[dict[str, Any]]:
    results = []
    for channel, backend, probe in _CHECKS:
        t0 = time.perf_counter()
        status, note = "OK", ""
        try:
            r = probe()
            if channel == "wechat":
                if r.status_code == 200:
                    note, status = "HTTP 200", "OK"
                else:
                    note, status = f"HTTP {r.status_code}", "BLOCKED"
            else:
                note = f"{len(r)} items"
        except ZhiweiError as e:
            status, note = "BLOCKED", str(e)[:80]
        except Exception as e:  # noqa: BLE001
            status, note = "ERROR", f"{type(e).__name__}: {str(e)[:60]}"
        results.append(
            {
                "channel": channel,
                "backend": backend,
                "status": status,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
                "note": note,
            }
        )
    return results


def report(results: list[dict[str, Any]] | None = None) -> str:
    from .output import md_table

    rows = [
        [r["channel"], r["backend"], r["status"], f"{r['latency_ms']}ms", r["note"]]
        for r in (results or check_all())
    ]
    return md_table(["渠道", "后端", "状态", "耗时", "说明"], rows)
