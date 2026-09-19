"""单元测试：解析逻辑全部离线可测；真实网络用 live 标记（默认跳过）."""

from __future__ import annotations

import os

import pytest

from zhiwei.channels.weibo import _clean_post, _parse_hot_ajax, _parse_hot_mobile, _parse_post_ref
from zhiwei.channels.zhihu import _clean_hot_item, parse_question_id
from zhiwei.channels.wechat import _extract
from zhiwei.output import strip_html, truncate

# ---------------- 知乎 ----------------


def test_parse_question_id_forms():
    assert parse_question_id("639662261") == 639662261
    assert parse_question_id(" https://www.zhihu.com/question/639662261 ") == 639662261
    assert parse_question_id("https://www.zhihu.com/question/123/answer/456") == 123
    assert parse_question_id("https://api.zhihu.com/questions/999") == 999


def test_clean_hot_item():
    entry = {
        "detail_text": "1234 万热度",
        "card_label": [{"text": "热"}, {"text": "新"}],
        "target": {
            "id": 123,
            "title": "  测试话题  ",
            "excerpt": "<b>摘要</b>内容",
            "answer_count": 42,
            "follower_count": 7,
        },
    }
    item = _clean_hot_item(entry)
    assert item["title"] == "测试话题"
    assert item["url"] == "https://www.zhihu.com/question/123"
    assert item["excerpt"] == "摘要内容"
    assert item["tags"] == ["热", "新"]
    assert item["heat"] == "1234 万热度"


# ---------------- 微博 ----------------


def test_parse_post_ref():
    assert _parse_post_ref("5123456789012345") == "5123456789012345"
    assert _parse_post_ref("https://m.weibo.cn/status/AbCdEf123") == "AbCdEf123"
    assert _parse_post_ref("https://weibo.com/1234567/AbCdEf123?from=feed") == "AbCdEf123"
    assert _parse_post_ref("https://m.weibo.cn/status/5123456789012345") == "5123456789012345"


def test_hot_ajax_parser():
    payload = {
        "data": {
            "realtime": [
                {"rank": 1, "word": "测试话题", "note": "详情", "num": 999, "label_name": "爆"},
                {"rank": 2, "word": "第二话题", "num": 888},
            ]
        }
    }
    out = _parse_hot_ajax(payload, 50)
    assert out[0]["label"] == "爆" and out[0]["heat"] == 999
    assert out[1]["word"] == "第二话题" and out[1]["heat"] == 888
    assert "s.weibo.com" in out[0]["url"]
    with pytest.raises(ValueError):
        _parse_hot_ajax({"data": {"realtime": []}}, 10)


def test_hot_mobile_parser_and_clean_post():
    payload = {
        "data": {
            "cards": [
                {
                    "card_group": [
                        {"desc": "话题A", "desc_extran": "123万", "scheme": "sinaweibo://searchall"},
                        {"desc": "话题B"},
                        {"desc": ""},
                    ]
                }
            ]
        }
    }
    out = _parse_hot_mobile(payload, 50)
    assert [e["word"] for e in out] == ["话题A", "话题B"]
    assert out[0]["note"] == "123万"

    post = _clean_post(
        {
            "user": {"screen_name": "某人", "description": "简介"},
            "created_at": "Wed Sep 20 12:00:00 +0800 2026",
            "text": "<span>正文<b>加粗</b></span>",
            "reposts_count": 1,
            "comments_count": 2,
            "attitudes_count": 3,
            "source": " iPhone客户端 ",
        }
    )
    assert post["author"] == "某人"
    assert post["content"] == "正文加粗"
    assert post["likes"] == 3 and post["source"] == "iPhone客户端"


# ---------------- 公众号 ----------------

WECHAT_HTML = """
<html><head>
<meta property="og:title" content="深度好文"/>
<meta property="og:article:author" content="某公众号"/>
</head><body>
<h1 id="activity-name">深度好文</h1>
<em id="publish_time">2026年9月20日</em>
<div id="js_content">
  <p>第一段正文，讲清楚了核心观点与来龙去脉，包含足够的细节。</p>
  <p>第二段：用数据支撑观点，并给出可复核的引用来源说明。</p>
  <script>alert(1)</script>
</div>
</body></html>
"""


def test_wechat_extract():
    art = _extract(WECHAT_HTML, "https://mp.weixin.qq.com/s/abc")
    assert art["title"] == "深度好文"
    assert art["account"] == "某公众号"
    assert art["publish_time"] == "2026年9月20日"
    assert "第一段正文" in art["content"]
    assert "alert" not in art["content"]


def test_wechat_extract_rejects_verify_page():
    with pytest.raises(ValueError, match="验证页|js_content"):
        _extract("<html><title>环境异常</title><body>去验证</body></html>", "https://mp.weixin.qq.com/s/x")


# ---------------- 输出 ----------------


def test_truncate_and_strip():
    assert truncate("短文本", 10) == "短文本"
    long = "x" * 300
    t = truncate(long, 100)
    assert t.startswith("x" * 100) and "已截断" in t
    assert strip_html("<p>a</p><p>b</p>") in ("a\nb", "a\n\nb")


# ---------------- live 冒烟（ZHIWEI_LIVE=1 才跑） ----------------


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ZHIWEI_LIVE"), reason="需要 ZHIWEI_LIVE=1")
def test_live_zhihu_hot():
    from zhiwei.channels.zhihu import hot_list

    items, backend = hot_list(5)
    assert len(items) == 5 and items[0]["title"]
