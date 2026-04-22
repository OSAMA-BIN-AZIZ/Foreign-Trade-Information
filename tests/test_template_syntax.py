from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def test_all_jinja_templates_compile() -> None:
    template_dir = Path("app/render/templates")
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    template_names = [p.name for p in template_dir.glob("*.j2")]
    assert template_names, "No templates found in app/render/templates"

    for name in template_names:
        env.get_template(name)
