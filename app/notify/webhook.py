import httpx


async def notify_webhook(url: str, message: str, timeout: float = 10.0) -> None:
    if not url:
        return
    async with httpx.AsyncClient(timeout=timeout) as client:
        await client.post(url, json={"text": message})
