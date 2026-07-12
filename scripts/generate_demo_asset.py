from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from self_recovering_automation.cli import render_demo  # noqa: E402


def sanitize(text: str) -> str:
    text = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", r"C:\\Users\\[redacted]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", text)
    text = re.sub(r"\b[a-fA-F0-9]{24,}\b", "[redacted-id]", text)
    text = re.sub(r"(?i)(token|secret|password)=\S+", r"\1=[redacted]", text)
    return text


def main() -> None:
    from PIL import Image, ImageDraw, ImageFont

    lines = sanitize(render_demo()).splitlines()
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    content_width = max(measure.textlength(line, font=font) for line in lines)
    width, line_height = max(1040, int(content_width) + 72), 30
    height = 92 + len(lines) * line_height
    image = Image.new("RGB", (width, height), "#0b1220")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=16, outline="#334155", width=2)
    for x, color in ((28, "#fb7185"), (50, "#fbbf24"), (72, "#4ade80")):
        draw.ellipse((x - 7, 18, x + 7, 32), fill=color)
    for index, line in enumerate(lines):
        color = "#f8fafc"
        if "WARN" in line:
            color = "#fbbf24"
        elif "Result:" in line or "FINAL STATE" in line:
            color = "#86efac"
        draw.text((32, 56 + index * line_height), line, fill=color, font=font)
    output = ROOT / "assets" / "dry-run-dashboard.png"
    image.save(output, optimize=True)
    print(f"wrote {output.relative_to(ROOT)} from sanitized dry-run output")


if __name__ == "__main__":
    main()
