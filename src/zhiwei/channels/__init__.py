"""渠道层：每个平台一个模块，每个能力一个 backend 列表（首选 + 备选）.

约定：
- backend 是 ``(名字, 可调用)``，可调用返回结构化 dict/list，解析失败或平台报错就抛异常
- channel 入口按顺序尝试 backend，全部失败抛 ChannelError（doctor 据此报告）
"""

from . import wechat, weibo, zhihu

__all__ = ["wechat", "weibo", "zhihu"]
