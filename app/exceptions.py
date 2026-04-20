"""Custom exceptions."""

class AppError(Exception):
    """Base app error."""


class WeChatAPIError(AppError):
    def __init__(self, errcode: int, errmsg: str) -> None:
        super().__init__(f"wechat_api_error errcode={errcode} errmsg={errmsg}")
        self.errcode = errcode
        self.errmsg = errmsg


class PublishPermissionError(WeChatAPIError):
    """Permission error on publish endpoint."""
