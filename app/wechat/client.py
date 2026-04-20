from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.exceptions import WeChatAPIError, PublishPermissionError
from app.models import DraftArticle

BASE_URL = "https://api.weixin.qq.com/cgi-bin"


class WeChatClient:
    def __init__(self, app_id: str, app_secret: str, timeout: float = 10.0, mock: bool = True) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout = timeout
        self.mock = mock
        self._token: str | None = None
        self._token_expire_at: datetime | None = None
        self.logger = logging.getLogger(__name__)

    async def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and self._token_expire_at and self._token_expire_at > datetime.now(timezone.utc):
            return self._token
        if self.mock:
            self._token = "mock_access_token"
            self._token_expire_at = datetime.now(timezone.utc) + timedelta(hours=1)
            return self._token
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{BASE_URL}/token",
                params={"grant_type": "client_credential", "appid": self.app_id, "secret": self.app_secret},
            )
            data = resp.json()
            self._ensure_ok(data)
            self._token = data["access_token"]
            self._token_expire_at = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 7200)) - 60)
            return self._token

    async def upload_temp_image(self, path: str) -> dict:
        return await self._upload_image(path, temporary=True)

    async def upload_article_image(self, path: str) -> dict:
        return await self._upload_image(path, temporary=False)

    async def _upload_image(self, path: str, temporary: bool) -> dict:
        Path(path).exists() or (_ for _ in ()).throw(FileNotFoundError(path))
        if self.mock:
            return {"type": "image", "media_id": f"mock_media_{Path(path).stem}", "url": f"https://mmbiz.qpic.cn/{Path(path).name}"}
        token = await self.get_access_token()
        endpoint = "media/upload" if temporary else "media/uploadimg"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(path, "rb") as f:
                files = {"media": (Path(path).name, f, "image/jpeg")}
                resp = await client.post(f"{BASE_URL}/{endpoint}", params={"access_token": token, "type": "image"}, files=files)
            data = resp.json()
            self._ensure_ok(data)
            return data

    async def add_draft(self, article: DraftArticle) -> dict:
        if self.mock:
            return {"media_id": "mock_draft_media_id"}
        token = await self.get_access_token()
        payload = {"articles": [article.model_dump()]}
        return await self._post_with_retry("draft/add", payload, token)

    async def submit_freepublish(self, media_id: str) -> dict:
        if self.mock:
            return {"publish_id": f"mock_publish_{media_id}"}
        token = await self.get_access_token()
        return await self._post_with_retry("freepublish/submit", {"media_id": media_id}, token)

    async def get_publish_status(self, publish_id: str) -> dict:
        if self.mock:
            return {"publish_id": publish_id, "publish_status": 0, "article_id": "mock_article_id"}
        token = await self.get_access_token()
        return await self._post_with_retry("freepublish/get", {"publish_id": publish_id}, token)

    async def _post_with_retry(self, endpoint: str, payload: dict, token: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{BASE_URL}/{endpoint}", params={"access_token": token}, json=payload)
            data = resp.json()
            if data.get("errcode") == 40001:
                token = await self.get_access_token(force_refresh=True)
                resp = await client.post(f"{BASE_URL}/{endpoint}", params={"access_token": token}, json=payload)
                data = resp.json()
            if data.get("errcode") in {48001, 85019, 20012}:
                raise PublishPermissionError(int(data.get("errcode")), data.get("errmsg", "permission denied"))
            self._ensure_ok(data)
            return data

    def _ensure_ok(self, data: dict) -> None:
        errcode = int(data.get("errcode", 0))
        if errcode != 0:
            raise WeChatAPIError(errcode, data.get("errmsg", "unknown"))
