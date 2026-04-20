import pytest

from app.wechat.client import WeChatClient
from app.wechat.media import upload_cover


@pytest.mark.asyncio
async def test_upload_cover_uses_thumb_endpoint(tmp_path) -> None:
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"x")
    client = WeChatClient("", "", mock=True)
    media_id = await upload_cover(client, str(img))
    assert media_id.startswith("mock_thumb_")
