from app.models import DraftArticle
from app.wechat.client import WeChatClient


async def create_draft(client: WeChatClient, article: DraftArticle) -> str:
    data = await client.add_draft(article)
    return data["media_id"]
