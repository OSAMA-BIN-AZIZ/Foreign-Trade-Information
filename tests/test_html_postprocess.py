from pathlib import Path
from app.render.html_postprocess import replace_local_images


def test_html_image_replace(tmp_path: Path) -> None:
    p = tmp_path / "img.png"
    p.write_bytes(b"x")
    html = f'<p><img src="{p}" /></p>'
    out = replace_local_images(html, uploader=lambda _: "https://mmbiz.qpic.cn/abc")
    assert "https://mmbiz.qpic.cn/abc" in out
