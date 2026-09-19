"""CLI —— agent 与人共用的入口。默认输出 markdown，--json 输出结构化数据."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from . import digest, summary
from .channels import wechat, weibo, zhihu
from .doctor import check_all, report as doctor_report
from .output import meta, render


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="输出 JSON 而非 markdown")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zhiwei",
        description="知微 — 给 AI Agent 的中文互联网深度层 (只读公开内容)",
    )
    parser.add_argument("--version", action="version", version=f"zhiwei {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("zhihu-hot", help="知乎热榜")
    p.add_argument("--limit", type=int, default=50)
    _add_common(p)

    p = sub.add_parser("zhihu-question", help="知乎问题 + 高赞回答")
    p.add_argument("target", help="问题 ID 或链接")
    p.add_argument("--answers", type=int, default=5, help="抓取回答数(默认5)")
    _add_common(p)

    p = sub.add_parser("weibo-hot", help="微博热搜")
    p.add_argument("--limit", type=int, default=50)
    _add_common(p)

    p = sub.add_parser("weibo-post", help="微博博文正文")
    p.add_argument("target", help="帖子 ID 或链接")
    _add_common(p)

    p = sub.add_parser("wechat-article", help="公众号单篇文章 → markdown")
    p.add_argument("target", help="文章 URL 或本地 HTML 路径")
    _add_common(p)

    p = sub.add_parser("zhihu-digest", help="观点聚合：问题高赞回答的立场图谱")
    p.add_argument("target", help="问题 ID 或链接")
    p.add_argument("--answers", type=int, default=10, help="参与聚合的回答数(默认10)")
    p.add_argument(
        "--llm",
        action="store_true",
        help="用 ZHIWEI_LLM_* 环境变量指定的模型增强聚合(失败自动降级)",
    )
    _add_common(p)

    p = sub.add_parser("wechat-summary", help="公众号文章 → TextRank 摘要 + 关键数据点")
    p.add_argument("target", help="文章 URL 或本地 HTML 路径")
    p.add_argument("--sentences", type=int, default=5, help="摘要句数(默认5)")
    _add_common(p)

    p = sub.add_parser("snapshot", help="抓取知乎热榜并存入本地快照（时间线地基，建议定时运行）")
    p.add_argument("--limit", type=int, default=50)
    _add_common(p)

    p = sub.add_parser("timeline", help="回放某话题在历史快照中的排名/热度演化")
    p.add_argument("keyword", help="话题关键词（标题模糊匹配）")
    p.add_argument("--limit", type=int, default=50)
    _add_common(p)

    p = sub.add_parser("doctor", help="各渠道各后端健康检查")
    _add_common(p)

    return parser


def run(args: argparse.Namespace) -> int:
    as_json = getattr(args, "json", False)
    try:
        if args.command == "zhihu-hot":
            items, backend = zhihu.hot_list(args.limit)
            m = meta("https://www.zhihu.com/hot", backend)
            data = {"meta": m, "items": items}
            out = render(
                f"知乎热榜 Top {len(items)}",
                [zhihu.hot_markdown(items), "", f"backend: {backend} · {m['fetched_at']}"],
                data,
                as_json,
            )
        elif args.command == "zhihu-question":
            qid = zhihu.parse_question_id(args.target)
            detail, answers, backend, note = zhihu.question(qid, args.answers)
            m = meta(detail["url"], backend)
            data = {"meta": m, "question": detail, "answers": answers}
            sections = [zhihu.question_markdown(detail, answers), "", f"backend: {backend}"]
            if note:
                sections = [f"> ⚠️ {note}", ""] + sections
            out = render(detail["title"], sections, data, as_json)
        elif args.command == "weibo-hot":
            items, backend = weibo.hot_search(args.limit)
            m = meta("https://weibo.com/hot/search", backend)
            data = {"meta": m, "items": items}
            out = render(
                f"微博热搜 Top {len(items)}",
                [weibo.hot_markdown(items), "", f"backend: {backend} · {m['fetched_at']}"],
                data,
                as_json,
            )
        elif args.command == "weibo-post":
            post, backend = weibo.post(args.target)
            data = {"meta": meta(post["url"], backend), "post": post}
            out = render(f"@{post['author']} 的微博", [weibo.post_markdown(post)], data, as_json)
        elif args.command == "wechat-article":
            art, backend = wechat.article(args.target)
            data = {"meta": meta(art["url"], backend), **art}
            out = render(
                art["title"],
                [f"- 公众号: {art['account']} · 发布: {art['publish_time'] or '未知'}", "", art["content"]],
                data,
                as_json,
            )
        elif args.command == "zhihu-digest":
            qid = zhihu.parse_question_id(args.target)
            detail, answers, backend, note = zhihu.question(qid, args.answers)
            d = digest.digest(answers)
            m = meta(detail["url"], backend)
            sections = [digest.digest_markdown(detail["title"], d)]
            llm_note = ""
            if getattr(args, "llm", False):
                enh, llm_note = digest.llm_enhance(detail["title"], d)
                if enh:
                    sections.insert(1, f"\n## 🤖 LLM 增强\n\n{enh}\n")
            sections += ["", f"backend: {backend}"]
            if note:
                sections = [f"> ⚠️ {note}", ""] + sections
            if llm_note:
                sections += ["", f"> {llm_note}"]
            data = {"meta": m, "digest": d, "llm_note": llm_note}
            out = render(f"观点聚合：{detail['title']}", sections, data, as_json)
        elif args.command == "wechat-summary":
            art, backend = wechat.article(args.target)
            s = summary.summarize(art["content"], args.sentences)
            m = meta(art["url"], backend)
            data = {"meta": m, "summary": s, **art}
            meta_line = f"- 公众号: {art['account']} · 发布: {art['publish_time'] or '未知'} · backend: {backend}"
            out = render(
                art["title"],
                [summary.summary_markdown(art["title"], meta_line, s)],
                data,
                as_json,
            )
        elif args.command == "snapshot":
            from . import storage

            items, backend = zhihu.hot_list(args.limit)
            result = storage.save_snapshot(items, backend)
            data = {"result": result, "items": items}
            out = render(
                f"快照已保存 {result['ts']}",
                [
                    f"- 本份 {result['saved']} 条，其中 **{result['new']} 条**是上次快照之后新进榜的",
                    f"- 累计 {result['total_snapshots']} 份快照 / {result['total_rows']} 行，库：{storage.db_path()}",
                    "",
                    "让时间线长出价值：用任务计划/cron 每小时跑一次 `zhiwei snapshot`，"
                    "然后用 `zhiwei timeline <关键词>` 回放演化。",
                ],
                data,
                as_json,
            )
        elif args.command == "timeline":
            from . import storage

            st = storage.stats()
            rows = storage.timeline(args.keyword, args.limit)
            data = {"stats": st, "rows": rows}
            out = render(
                f"时间线：{args.keyword}",
                [storage.timeline_markdown(args.keyword, rows, st)],
                data,
                as_json,
            )
        elif args.command == "doctor":
            results = check_all()
            data = {"results": results}
            out = render("zhiwei doctor", [doctor_report(results)], data, as_json)
        else:  # pragma: no cover
            out = f"未知命令 {args.command}"
        print(out)
        return 0
    except Exception as e:  # noqa: BLE001 — CLI 边界，统一给出可读错误
        print(f"error: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台缺省 GBK，强制 UTF-8 避免 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
