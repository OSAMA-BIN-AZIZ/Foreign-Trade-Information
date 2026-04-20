from app.wechat.client import WeChatClient


async def get_token(client: WeChatClient) -> str:
    return await client.get_access_token()
