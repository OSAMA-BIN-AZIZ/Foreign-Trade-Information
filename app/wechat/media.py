from app.wechat.client import WeChatClient


async def upload_cover(client: WeChatClient, path: str) -> str:
    data = await client.upload_thumb(path)
    return data["media_id"]


async def upload_body_image(client: WeChatClient, path: str) -> str:
    data = await client.upload_article_image(path)
    return data.get("url", "")
