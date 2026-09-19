# 发布与推广手册（内部执行用）

> v0.1 已发布到 GitHub。本文件是剩余分发动作的执行清单与现成文案——按顺序做，每项 10 分钟以内。

## 1. 发布 PyPI（`pip install zhiwei` 的前提）

1. 在 [pypi.org](https://pypi.org) 注册账号，开启 2FA
2. GitHub 仓库 → Settings → Secrets → 添加 `PYPI_API_TOKEN`（PyPI 账号设置里生成）
3. 恢复 CI 后（见 `docs/ci.yml.example` 提交说明），新增发布 workflow，或本地手动发：
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```
4. PyPI 项目名 `zhiwei` 若被占用：用 `zhiwei-mcp` 或 `zhiwei-cli` 作为包名（改 pyproject 的 name，import 名不变）
5. 发布后更新 install.md 与 README 的安装命令为 `pip install zhiwei`

## 2. MCP 目录提交（现成文案）

**一句话（EN）**：ZhiWei — Chinese-web depth layer for AI agents. Zhihu hot list & Q&A stance digests, Weibo hot search, WeChat article TextRank summaries. Public content only, CLI + MCP (8 tools, 2 workflow prompts).

**一句话（中文）**：知微 — 给 AI Agent 的中文互联网深度层。知乎热榜/观点聚合、微博热搜、公众号 TextRank 摘要。只读公开内容，CLI + MCP。

**关键信息**：command `zhiwei-mcp`（stdio）· 8 tools + 2 prompts + 1 resource · Python ≥3.10 · MIT

渠道：[glama.ai/mcp/servers](https://glama.ai/mcp/servers) → Submit · [smithery.ai](https://smithery.ai) → 按其 GitHub 集成流程 · [mcp.so](https://mcp.so) → Submit · [PulseMCP](https://pulsemcp.com) → 提交表单。另投 awesome-claude-code-mcp-servers、awesome-mcp-servers 的 PR。

## 3. Agent-Reach 渠道提案（issue 草稿，国内网络验证后再发）

> 标题：提案：知乎/微博/公众号的深度后端（zhiwei）
>
> 你们的能力层架构里，知乎、微博、公众号目前缺少可靠后端。我们在做一个专注中文内容深度提取的项目 zhiwei（github.com/0718lol/zhiwei，MIT）：知乎热榜双后端（api.zhihu.com 主备路由，已稳定运行）、知乎问答（API + Jina 中继多路）、微博热搜双后端、公众号单篇解析，全部只读公开内容、无登录态，并自带 doctor 自诊断与多后端降级——与你们"首选+备选路由"的设计完全同构。
>
> 如果方向认可，我们可以把 zhiwei 的渠道能力按你们的 channel 规范封装成后端，供 agent-reach doctor 调用；也欢迎直接取用我们的解析逻辑。深度能力（观点聚合/评论树/时间线）我们会持续做在 zhiwei 侧，不重复造轮子。

## 4. 国内网络验证清单（最高优先级）

- [ ] `pip install -e ".[mcp,dev]" && zhiwei doctor` — 微博双后端、知乎问答是否变绿
- [ ] 真实公众号文章：微信内复制链接 → `zhiwei wechat-summary <链接>`
- [ ] 热榜问题 → `zhiwei zhihu-digest <问题链接>` 真实数据跑通
- [ ] 配置定时任务：Windows 任务计划 / cron 每小时 `zhiwei snapshot`（时间线数据从今天开始积累）
