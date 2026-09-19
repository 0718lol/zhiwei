"""本地时间线存储 —— 热点时间线的地基（v0.2 提前动工）.

壁垒不是代码，是持续运行的时间：每次 `zhiwei snapshot` 把知乎热榜落一份
本地 SQLite 快照，`zhiwei timeline` 回放某个话题的排名/热度演化.

- 零第三方依赖（stdlib sqlite3），库默认在 ~/.zhiwei/timeline.db（local-first，
  不进仓库），可用 ZHIWEI_DB 环境变量覆盖.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  rank INTEGER NOT NULL,
  title TEXT NOT NULL,
  url TEXT,
  heat TEXT,
  answer_count INTEGER,
  backend TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshots_title ON snapshots(title);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
"""


def db_path() -> Path:
    override = os.environ.get("ZHIWEI_DB")
    if override:
        return Path(override)
    return Path.home() / ".zhiwei" / "timeline.db"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_snapshot(
    items: list[dict[str, Any]], backend: str, path: Path | None = None
) -> dict[str, Any]:
    """落一份快照. 返回 {ts, saved, new, total_snapshots, total_rows}.

    new = 与上一份快照对比新出现的话题数（首份快照全部算新）.
    """
    conn = _connect(path)
    # 微秒精度：连续两次 snapshot 也不碰撞（展示时只截到分钟）
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")
    prev = conn.execute("SELECT title FROM snapshots WHERE ts = (SELECT MAX(ts) FROM snapshots)")
    prev_titles = {r["title"] for r in prev}
    new = 0
    for i, it in enumerate(items, 1):
        is_new = it["title"] not in prev_titles
        new += int(is_new)
        conn.execute(
            "INSERT INTO snapshots (ts, rank, title, url, heat, answer_count, backend)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                ts,
                i,
                it["title"],
                it.get("url"),
                it.get("heat"),
                it.get("answer_count"),
                backend,
            ),
        )
    conn.commit()
    total_snapshots = conn.execute("SELECT COUNT(DISTINCT ts) c FROM snapshots").fetchone()["c"]
    total_rows = conn.execute("SELECT COUNT(*) c FROM snapshots").fetchone()["c"]
    conn.close()
    return {
        "ts": ts,
        "saved": len(items),
        "new": new,
        "total_snapshots": total_snapshots,
        "total_rows": total_rows,
    }


def timeline(keyword: str, limit: int = 50, path: Path | None = None) -> list[dict[str, Any]]:
    """某话题（标题模糊匹配）的历史出现记录，按时间倒序."""
    conn = _connect(path)
    rows = conn.execute(
        "SELECT ts, rank, title, url, heat, answer_count, backend FROM snapshots"
        " WHERE title LIKE ? ORDER BY ts DESC, rank ASC LIMIT ?",
        (f"%{keyword}%", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats(path: Path | None = None) -> dict[str, Any]:
    """库的整体状态：快照份数、时间跨度、行数."""
    conn = _connect(path)
    row = conn.execute(
        "SELECT COUNT(DISTINCT ts) snapshots, COUNT(*) rows,"
        " MIN(ts) first_ts, MAX(ts) last_ts FROM snapshots"
    ).fetchone()
    conn.close()
    return {
        "snapshots": row["snapshots"],
        "rows": row["rows"],
        "first_ts": row["first_ts"],
        "last_ts": row["last_ts"],
        "db": str(path or db_path()),
    }


def timeline_markdown(keyword: str, rows: list[dict[str, Any]], st: dict[str, Any]) -> str:
    if not rows:
        return (
            f"暂无包含「{keyword}」的快照记录。先运行 `zhiwei snapshot` 积累数据"
            f"（当前库：{st['snapshots']} 份快照 / {st['rows']} 行）。"
        )
    seen_ts: set[str] = set()
    lines = [
        f"话题「{keyword}」共出现 {len(rows)} 次（{st['snapshots']} 份快照，"
        f"{st['first_ts']} → {st['last_ts']}）",
        "",
        "| 时间 | 当次排名 | 话题 | 热度 | 回答数 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        first = "" if r["ts"] in seen_ts else r["ts"][:16].replace("T", " ")
        seen_ts.add(r["ts"])
        lines.append(
            f"| {first} | #{r['rank']} | [{r['title']}]({r['url'] or '#'}) "
            f"| {r['heat'] or '-'} | {r['answer_count'] if r['answer_count'] is not None else '-'} |"
        )
    return "\n".join(lines)
