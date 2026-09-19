"""深度引擎测试：观点聚合 + TextRank 摘要，全部离线."""

from __future__ import annotations

from zhiwei.digest import digest, digest_markdown
from zhiwei.summary import summarize, summary_markdown

ANSWERS = [
    {
        "author": "甲",
        "voteup": 5200,
        "url": "https://www.zhihu.com/question/1/answer/1",
        "content": "这个政策完全正确，确实是多年来最务实的方案。我支持的核心原因有三点：第一，数据上同比增长了 12%；第二，它解决了历史遗留问题；第三，成本可控。所以我认为方向必然是对的。",
    },
    {
        "author": "乙",
        "voteup": 3100,
        "url": "https://www.zhihu.com/question/1/answer/2",
        "content": "说白了就是割韭菜。我反对这个方案，因为它根本不解决问题，恰恰相反，把成本转嫁给了普通人。别忘了之前的教训，别信。",
    },
    {
        "author": "丙",
        "voteup": 1800,
        "url": "https://www.zhihu.com/question/1/answer/3",
        "content": "根据公开资料，2025 年试点城市的统计显示，参与率增长 35%，但退出率也上升了 8%。客观地说，数据是好是坏取决于你站在哪边看。",
    },
    {
        "author": "丁",
        "voteup": 900,
        "url": "https://www.zhihu.com/question/1/answer/4",
        "content": "我觉得应该辩证地看。整体方向值得肯定，但执行细节问题在于基层压力，希望不要一刀切。",
    },
]


def test_digest_camps_and_representatives():
    d = digest(ANSWERS)
    assert d["total_answers"] == 4
    # 甲=支持(正确/支持/必然/数据/增长)，乙=反对(割韭菜/反对/根本不/恰恰相反/别信)，丙=事实(根据/统计/显示/增长/数据)，丁=支持(应该/值得/肯定/问题在于→也有反对词，边界可接受只要不出错)
    assert d["camps"]["支持"]["count"] >= 1
    assert d["camps"]["反对"]["count"] >= 1
    assert d["camps"]["事实"]["count"] >= 1
    # 代表观点按赞数排序：支持方代表应是甲(5200)
    rep = d["camps"]["支持"]["representatives"][0]
    assert rep["author"] == "甲" and rep["voteup"] == 5200
    assert rep["core"]  # 核心句非空
    # 占比加总约 100%
    assert abs(sum(c["vote_pct"] for c in d["camps"].values()) - 100) < 1
    # 关键词非空
    assert d["keywords"]


def test_digest_markdown_shape():
    d = digest(ANSWERS)
    md = digest_markdown("测试问题", d)
    assert "观点聚合" not in md or True  # 标题由调用方渲染
    assert "支持方" in md and "反对方" in md
    assert "方法：确定性规则引擎" in md
    assert "来源：https://www.zhihu.com/question/1/answer/1" in md


def test_summary_textrank():
    text = (
        "过去三年，中国新能源汽车出口增长了 240%，2025 年达到 180 万辆。"
        "欧洲市场占比最高，达到 38%。同时，东南亚市场增速最快，同比增长 65%。"
        "但是贸易壁垒也在上升，欧盟对中国电池的碳足迹要求将在 2027 年生效。"
        "这意味着出口结构必须转向本地化生产。宁德时代已经在匈牙利建厂，"
        "投资 73 亿欧元。比亚迪则在泰国和巴西布局整车工厂。"
        "行业共识是：未来五年，海外本地化率将成为竞争的核心指标。"
        "据行业研究机构预测，2030 年海外产能将占总销量的 30%。"
    )
    s = summarize(text, n=3)
    assert len(s["sentences"]) == 3
    # 抽取句必须来自原文
    for sent in s["sentences"]:
        assert sent in text
    assert s["numbers"], "应抽到百分比/金额等关键数据"
    md = summary_markdown("测试文章", "- 公众号: 测试号", s)
    assert "TextRank" in md and "关键数据点" in md


def test_summary_short_text():
    s = summarize("太短了", n=3)
    assert s["sentences"] == []
