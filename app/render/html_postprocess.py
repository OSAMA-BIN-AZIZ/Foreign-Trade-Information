from pathlib import Path
from bs4 import BeautifulSoup


def replace_local_images(html: str, uploader: callable | None = None, cache: dict[str, str] | None = None) -> str:
    cache = cache or {}
    soup = BeautifulSoup(html, "lxml")
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("http"):
            continue
        if src in cache:
            img["src"] = cache[src]
            continue
        if uploader and Path(src).exists():
            new_url = uploader(src)
            cache[src] = new_url
            img["src"] = new_url
    for tag in soup.find_all(True):
        allowed = {"p", "ul", "ol", "li", "strong", "em", "h1", "h2", "h3", "blockquote", "a", "img"}
        if tag.name not in allowed:
            tag.unwrap()
        if tag.name == "a":
            tag["rel"] = "nofollow noopener"
    return str(soup)
