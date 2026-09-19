"""MCP server —— 把知微的能力暴露给任意 coding agent.

依赖可选: pip install "zhiwei[mcp]"（官方 mcp SDK / FastMCP, stdio 传输）.
"""

from __future__ import annotations

from .channels import wechat, weibo, zhihu
from .doctor import report as doctor_report


def main() -> int:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print('MCP SDK 未安装。请运行: pip install "zhiwei[mcp]"', file=__import__("sys").stderr)
        return 1

    mcp = FastMCP(
        "zhiwei",
        instructions=(
            "知微：中文互联网深度层（知乎/微博/微信公众号，只读公开内容）。"
            "输出为 LLM 优化的 markdown。先用 doctor 检查渠道可用性，再按需调用。"
        ),
    )

    @mcp.tool()
    def zhihu_hot_list(limit: int = 20) -> str:
        """知乎热榜：当前热门话题、热度与回答数. limit<=50."""
        items, backend = zhihu.hot_list(max(1, min(limit, 50)))
        return f"(backend: {backend})\n\n{zhihu.hot_markdown(items)}"

    @mcp.tool()
    def zhihu_question(target: str, max_answers: int = 5) -> str:
        """知乎问题详情 + 按 SDK 默认排序的高赞回答正文. target 为问题 ID 或链接."""
        qid = zhihu.parse_question_id(target)
        detail, answers, backend, note = zhihu.question(qid, max(1, min(max_answers, 20)))
        head = f"⚠️ {note}\n\n" if note else ""
        return f"{head}(backend: {backend})\n\n{zhihu.question_markdown(detail, answers)}"

    @mcp.tool()
    def weibo_hot_search(limit: int = 20) -> str:
        """微博热搜榜：话题、标签、热度. limit<=50."""
        items, backend = weibo.hot_search(max(1, min(limit, 50)))
        return f"(backend: {backend})\n\n{weibo.hot_markdown(items)}"

    @mcp.tool()
    def weibo_post(target: str) -> str:
        """微博博文正文与互动数据. target 为帖子 ID 或链接（不含评论区）."""
        post, backend = weibo.post(target)
        return f"(backend: {backend})\n\n{weibo.post_markdown(post)}"

    @mcp.tool()
    def wechat_article(target: str) -> str:
        """微信公众号单篇文章 → 干净 markdown 全文. target 为文章 URL 或本地 HTML 路径."""
        art, backend = wechat.article(target)
        return f"(backend: {backend})\n\n{wechat.article_markdown(art)}"

    @mcp.tool()
    def zhihu_digest(target: str, max_answers: int = 10, use_llm: bool = False) -> str:
        """观点聚合：把一个知乎问题的高赞回答聚合成立场图谱（支持/反对/事实三阵营
        占比 + 各阵营代表观点 + 焦点关键词）。确定性规则引擎，输出供进一步综合判断.
        use_llm=True 时用 ZHIWEI_LLM_* 环境变量指定的模型增强（失败自动降级）.
        target 为问题 ID 或链接."""
        from . import digest as digest_mod

        qid = zhihu.parse_question_id(target)
        detail, answers, backend, note = zhihu.question(qid, max(1, min(max_answers, 20)))
        d = digest_mod.digest(answers)
        body = digest_mod.digest_markdown(detail["title"], d)
        tail = ""
        if use_llm:
            enh, llm_note = digest_mod.llm_enhance(detail["title"], d)
            if enh:
                body += f"\n\n## 🤖 LLM 增强\n\n{enh}"
            tail = f"\n\n> {llm_note}"
        head = f"⚠️ {note}\n\n" if note else ""
        return f"{head}(backend: {backend})\n\n{body}{tail}"

    @mcp.tool()
    def wechat_summary(target: str, sentences: int = 5) -> str:
        """公众号文章 → TextRank 抽取式摘要 + 关键数据点（确定性，无 LLM）.
        target 为文章 URL 或本地 HTML 路径."""
        from . import summary as summary_mod

        art, backend = wechat.article(target)
        s = summary_mod.summarize(art["content"], max(1, min(sentences, 15)))
        meta_line = f"- 公众号: {art['account']} · 发布: {art['publish_time'] or '未知'} · backend: {backend}"
        return summary_mod.summary_markdown(art["title"], meta_line, s)

    @mcp.tool()
    def doctor() -> str:
        """各渠道各后端健康检查（状态/耗时/被拦原因）. 排查问题时先调用."""
        return doctor_report()

    # ---- MCP prompts：把"工具"升格成"工作流模板"，agent 一键调用 ----

    @mcp.prompt()
    def daily_brief(topic: str = "AI") -> str:
        """舆情晨报：热点 + 观点分歧的完整简报工作流."""
        return (
            f"请为用户生成一份关于「{topic}」的中文舆情晨报：\n"
            "1. 调用 zhihu_hot_list(limit=20)，筛选与该主题相关的条目\n"
            "2. 对最相关的 2-3 个问题调用 zhihu_digest 获取立场图谱\n"
            "3. 输出三部分：① 今日热点 Top5（标题+热度+链接）；"
            "② 重点议题的观点分歧（三阵营占比 + 各方代表观点）；③ 一段话总结\n"
            "要求：保留原始链接；某渠道 BLOCKED 时如实说明，不要静默跳过。"
        )

    @mcp.prompt()
    def article_deep_read(url: str) -> str:
        """公众号文章深度阅读：摘要 + 论点 + 追问."""
        return (
            f"请深度阅读这篇公众号文章：\n"
            f'1. 调用 wechat_summary(target="{url}", sentences=8)\n'
            "2. 输出四部分：① 一句话定位（这篇文章在讲什么）；"
            "② 核心论点（≤3 条，用作者原句支撑）；③ 关键数据点清单；"
            "④ 值得追问的 2 个问题（文章没说清或可能站不住的地方）"
        )

    # ---- MCP resource：agent 可随时读取的渠道状态 ----

    @mcp.resource("zhiwei://doctor")
    def doctor_resource() -> str:
        """zhiwei 各渠道各后端的当前健康状态."""
        return doctor_report()

    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
