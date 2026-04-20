import asyncio
from app.wechat.client import WeChatClient


async def submit_publish(client: WeChatClient, media_id: str) -> str:
    data = await client.submit_freepublish(media_id)
    return data["publish_id"]


async def poll_publish_status(client: WeChatClient, publish_id: str, max_tries: int = 6, interval: int = 2) -> dict:
    last = {}
    for _ in range(max_tries):
        last = await client.get_publish_status(publish_id)
        if int(last.get("publish_status", 0)) == 0:
            return last
        await asyncio.sleep(interval)
    return last
