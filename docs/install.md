# 安装 知微 (zhiwei)

> 这个文档是写给 AI Agent 执行的。用户只需要把本文件 URL 粘贴给你。

你的任务：为当前用户安装并验证 **知微 (zhiwei)** —— 给 agent 的中文互联网深度层（知乎/微博/微信公众号，只读公开内容）。

按以下步骤执行，每步失败就停下向用户报告。

## 步骤 1 — 检查环境

```bash
python --version   # 需要 >= 3.10
pip --version
```

没有 Python 就告诉用户去装（python.org 或系统包管理器），不要自行安装解释器。

## 步骤 2 — 安装（不修改系统配置）

优先 pipx / 用户级安装；在项目 venv 里则直接装进 venv：

```bash
pip install "zhiwei @ git+https://github.com/0718lol/zhiwei.git"
# 如需 MCP server 再加：
pip install "mcp>=1.2"
```

默认**只装进当前环境**，不要动系统包、不要写任何全局配置。
只有用户明确同意时才使用 `--system` / 全局路径。

## 步骤 3 — 验证

```bash
zhiwei --version
zhiwei doctor
```

`doctor` 会输出各渠道各后端的健康表。向用户逐行转述结果：

- OK 的渠道：直接可用；
- BLOCKED 的渠道：说明是平台风控/出口 IP 问题（常见于数据中心 IP 或代理 fake-ip），给出建议（换网络/直连）；
- 不要替用户反复重试被拦的接口。

## 步骤 4 —（可选）注册 MCP server

仅当用户要求时执行。Claude Code（`.mcp.json`）：

```json
{
  "mcpServers": {
    "zhiwei": {
      "command": "zhiwei-mcp",
      "args": []
    }
  }
}
```

Claude Desktop（`claude_desktop_config.json`）写同样的 server 配置。
注册后重启对应客户端，并用它的 MCP 列表确认 `zhiwei` 已连接。

## 完成标准

- `zhiwei doctor` 至少一个渠道 OK；
- 已向用户转述 doctor 结果与限制（只读公开内容、知乎问答受 IP 信誉影响、微博评论区未覆盖）。
