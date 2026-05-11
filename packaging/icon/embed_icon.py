"""Embed icon.png as base64 into kb_app/ui/resources/icon_data.py."""
import base64
import textwrap
from pathlib import Path

ROOT = Path(__file__).parents[2]
PNG  = Path(__file__).parent / "icon.png"

data = PNG.read_bytes()
b64  = base64.b64encode(data).decode()
lines = textwrap.wrap(b64, 76)

content  = '"""Auto-generated — run packaging/icon/embed_icon.py to refresh."""\n\n'
content += "ICON_PNG_B64: str = (\n"
for line in lines:
    content += f'    "{line}"\n'
content += ")\n"

resources = ROOT / "kb_app" / "ui" / "resources"
resources.mkdir(parents=True, exist_ok=True)
(resources / "__init__.py").write_text("", encoding="utf-8")
(resources / "icon_data.py").write_text(content, encoding="utf-8")
print(f"Written {len(b64)} chars to {resources / 'icon_data.py'}")
