---
name: zhiwei
description: 知微 — 给 AI Agent 的中文互联网深度层。知乎热榜/问答、微博热搜/博文、微信公众号文章的只读公开内容提取，输出 LLM 优化的 markdown。当用户要求调研知乎讨论、微博舆情热点或读取公众号文章时使用。
---

# 知微 (zhiwei)

给 AI Agent 的中文互联网深度层：**知乎 · 微博 · 微信公众号**。
只读公开内容、不用登录态、本地运行。所有命令默认输出 markdown（为 LLM 优化），加 `--json` 得到结构化数据。

## 何时用什么命令

| 用户想要… | 命令 |
|---|---|
| 看看知乎现在在热聊什么 | `zhiwei zhihu-hot --limit 20` |
| 深入某个知乎问题的主流观点 | `zhiwei zhihu-question <问题ID或链接> --answers 5` |
| **一个问题里大家吵什么、阵营占比如何** | `zhiwei zhihu-digest <问题ID或链接> --answers 10` |
| 看微博正在爆什么热点 | `zhiwei weibo-hot --limit 20` |
| 读一条微博的正文和互动数据 | `zhiwei weibo-post <帖子ID或链接>` |
| 读一篇公众号文章 | `zhiwei wechat-article <文章URL>` |
| **快速吸收一篇公众号长文的要点** | `zhiwei wechat-summary <文章URL> --sentences 5` |
| 某个命令报错了 | `zhiwei doctor` （先跑这个再排查） |

## 使用约定

1. **报错先跑 `zhiwei doctor`**：它会报告每个渠道每个后端的真实状态和被拦原因。某渠道 BLOCKED 时换其他渠道完成任务，并如实告知用户。
2. **输出可以很大**：热榜 `--limit` 默认 50，给用户摘要时先 `--limit 20`。
3. **知乎问答受 IP 信誉影响**：数据中心/代理 IP 下 answers 接口可能被风控（40362）。被拦时如实说明，不要反复重试。
4. **只读公开内容**：本工具不携带任何登录态。需要登录才能看的内容（微博评论区等）明确告知用户当前版本不覆盖。

## 示例

```bash
# 微博热榜前10
zhiwei weibo-hot --limit 10

# 从完整链接读知乎问题（自动提取 ID）
zhiwei zhihu-question "https://www.zhihu.com/question/639662261"

# 公众号文章转 markdown 存档
zhiwei wechat-article "https://mp.weixin.qq.com/s/xxxxx" > article.md
```
