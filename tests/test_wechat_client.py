import pytest
from app.models import DraftArticle
from app.wechat.client import WeChatClient


@pytest.mark.asyncio
async def test_wechat_mock_client(tmp_path) -> None:
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x")
    client = WeChatClient("", "", mock=True)
    token = await client.get_access_token()
    assert token
    up = await client.upload_temp_image(str(img))
    assert "media_id" in up
    draft = await client.add_draft(
        DraftArticle(title="t", author="a", digest="d", content="<p>c</p>", thumb_media_id="m")
    )
    assert draft["media_id"]
