from datetime import date
from pathlib import Path

from app.models import DailyDigest
from app.render.markdown_renderer import MarkdownRenderer
from app.render.html_postprocess import replace_local_images


class ArticleBuilder:
    def __init__(self, template_dir: Path) -> None:
        self.renderer = MarkdownRenderer(template_dir)

    def build(self, digest: DailyDigest) -> DailyDigest:
        md = self.renderer.render_markdown(
            {
                "title": digest.title,
                "date_line": digest.lunar_text,
                "usd_cny": digest.exchange_rate.usd_cny,
                "eur_cny": digest.exchange_rate.eur_cny,
                "news_items": digest.news_items,
            }
        )
        html = replace_local_images(self.renderer.markdown_to_html(md))
        digest.markdown = md
        digest.html = html
        return digest


def write_output(output_dir: Path, d: date, markdown_text: str, html_text: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{d.isoformat()}.md"
    html_path = output_dir / f"{d.isoformat()}.html"
    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return md_path, html_path
