"""时间线存储测试：临时库，完全离线."""

from __future__ import annotations

from zhiwei.storage import save_snapshot, stats, timeline, timeline_markdown

ITEMS_T1 = [
    {"title": "话题A：政策发布", "url": "https://www.zhihu.com/question/1", "heat": "100 万热度", "answer_count": 10},
    {"title": "话题B：行业观察", "url": "https://www.zhihu.com/question/2", "heat": "80 万热度", "answer_count": 5},
]
ITEMS_T2 = [
    {"title": "话题A：政策发布", "url": "https://www.zhihu.com/question/1", "heat": "300 万热度", "answer_count": 99},
    {"title": "话题C：新晋热点", "url": "https://www.zhihu.com/question/3", "heat": "50 万热度", "answer_count": 1},
]


def test_snapshot_dedupe_and_stats(tmp_path):
    db = tmp_path / "t.db"
    r1 = save_snapshot(ITEMS_T1, "test-backend", path=db)
    assert r1["saved"] == 2 and r1["new"] == 2  # 首份全算新
    r2 = save_snapshot(ITEMS_T2, "test-backend", path=db)
    assert r2["saved"] == 2
    assert r2["new"] == 1  # 话题A 已在上一份，话题C 是新的
    st = stats(path=db)
    assert st["snapshots"] == 2 and st["rows"] == 4
    assert st["first_ts"] <= st["last_ts"]


def test_timeline_query_and_markdown(tmp_path):
    db = tmp_path / "t.db"
    save_snapshot(ITEMS_T1, "b1", path=db)
    save_snapshot(ITEMS_T2, "b2", path=db)

    rows = timeline("话题A", path=db)
    assert len(rows) == 2
    # 按时间倒序：最新在前，且能看到热度从 100 万 → 300 万的爬升
    assert rows[0]["heat"] == "300 万热度" and rows[-1]["heat"] == "100 万热度"

    rows_c = timeline("话题C", path=db)
    assert len(rows_c) == 1

    assert timeline("不存在的关键词", path=db) == []

    st = stats(path=db)
    md = timeline_markdown("话题A", rows, st)
    assert "话题A：政策发布" in md and "300 万热度" in md


def test_timeline_markdown_empty(tmp_path):
    st = stats(path=tmp_path / "empty.db")
    md = timeline_markdown("任意词", [], st)
    assert "zhiwei snapshot" in md  # 空结果要引导用户先积累数据
