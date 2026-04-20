from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown import markdown


class MarkdownRenderer:
    def __init__(self, template_dir: Path) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(enabled_extensions=("html", "xml")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_markdown(self, ctx: dict) -> str:
        return self.env.get_template("daily_news.md.j2").render(**ctx)

    def markdown_to_html(self, md: str) -> str:
        return markdown(md)
