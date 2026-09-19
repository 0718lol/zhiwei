"""错误类型：渠道错误携带结构化上下文，供 CLI / MCP / doctor 呈现."""


class ZhiweiError(Exception):
    """Base error."""


class ChannelError(ZhiweiError):
    """A channel request failed after all backends."""

    def __init__(self, channel: str, message: str, backends_tried: list[str] | None = None):
        self.channel = channel
        self.backends_tried = backends_tried or []
        if self.backends_tried:
            detail = "；".join(self.backends_tried)
            message = f"{message} → {detail}"
        super().__init__(f"[{channel}] {message}")


class BlockedError(ChannelError):
    """The platform refused the request (anti-crawl / login wall / risk control)."""

    def __init__(self, channel: str, message: str, backends_tried: list[str] | None = None):
        super().__init__(channel, f"被平台拦截: {message}", backends_tried)
