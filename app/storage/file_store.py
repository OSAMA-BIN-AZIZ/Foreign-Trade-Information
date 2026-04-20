import json
from pathlib import Path


class FileImageCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def get(self) -> dict[str, str]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def set(self, mapping: dict[str, str]) -> None:
        self.path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
