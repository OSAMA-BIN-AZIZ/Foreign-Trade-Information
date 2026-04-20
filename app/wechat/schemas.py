from pydantic import BaseModel


class WeChatResponse(BaseModel):
    errcode: int = 0
    errmsg: str = "ok"


class AccessTokenResp(WeChatResponse):
    access_token: str = ""
    expires_in: int = 7200
