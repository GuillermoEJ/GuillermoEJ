import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pybonsai.options import AppConfig, RenderOptions, TreeOptions
from pybonsai.runner import generate_tree

OUTPUT_FILE = Path("bonsai.png")

WIDTH = 60
HEIGHT = 20
FONT_SIZE = 16
BG_COLOR = (13, 17, 23)
DEFAULT_COLOR = (201, 209, 217)


def get_font():
    try:
        return ImageFont.truetype("consola.ttf", FONT_SIZE)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", FONT_SIZE)
        except OSError:
            return ImageFont.load_default()


def parse_ansi_to_spans(raw: str) -> list[list[tuple[str, tuple[int, int, int]]]]:
    ansi_pattern = re.compile(r"\x1b\[([0-9;]*)m")
    lines_raw = raw.split("\n")

    parsed_lines = []
    current_color = DEFAULT_COLOR

    for line in lines_raw:
        spans = []
        pos = 0
        for match in ansi_pattern.finditer(line):
            start = match.start()
            if start > pos:
                spans.append((line[pos:start], current_color))
            code = match.group(1)
            if code in ("00", "0", ""):
                current_color = DEFAULT_COLOR
            elif code.startswith("38;2;"):
                parts = code.split(";")
                if len(parts) == 5:
                    current_color = (int(parts[2]), int(parts[3]), int(parts[4]))
            pos = match.end()

        if pos < len(line):
            spans.append((line[pos:], current_color))

        parsed_lines.append(spans)

    return parsed_lines


def trim_lines(parsed_lines):
    while parsed_lines and all(t.strip() == "" for t, _ in parsed_lines[-1]):
        parsed_lines.pop()
    while parsed_lines and all(t.strip() == "" for t, _ in parsed_lines[0]):
        parsed_lines.pop(0)

    min_indent = float("inf")
    for spans in parsed_lines:
        plain = "".join(text for text, _ in spans)
        stripped = plain.lstrip(" ")
        if stripped:
            min_indent = min(min_indent, len(plain) - len(stripped))

    if min_indent == float("inf"):
        min_indent = 0

    trimmed = []
    for spans in parsed_lines:
        to_strip = min_indent
        new_spans = []
        for text, color in spans:
            if to_strip >= len(text):
                to_strip -= len(text)
                continue
            if to_strip > 0:
                text = text[to_strip:]
                to_strip = 0
            new_spans.append((text, color))
        trimmed.append(new_spans)

    return trimmed


def render_png(parsed_lines) -> Image.Image:
    parsed_lines = trim_lines(parsed_lines)
    font = get_font()

    char_bbox = font.getbbox("M")
    char_w = char_bbox[2] - char_bbox[0]
    char_h = int((char_bbox[3] - char_bbox[1]) * 1.4)

    max_cols = max(sum(len(t) for t, _ in spans) for spans in parsed_lines) if parsed_lines else 0
    img_w = max_cols * char_w + 20
    img_h = len(parsed_lines) * char_h + 20

    img = Image.new("RGB", (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    for row_idx, spans in enumerate(parsed_lines):
        x = 10
        y = 10 + row_idx * char_h
        for text, color in spans:
            for ch in text:
                draw.text((x, y), ch, font=font, fill=color)
                x += char_w

    return img


def main():
    config = AppConfig(
        tree=TreeOptions(),
        render=RenderOptions(width=WIDTH, height=HEIGHT, instant=True),
    )
    generated = generate_tree(config)
    ansi_output = generated.to_ansi_string()
    parsed = parse_ansi_to_spans(ansi_output)
    img = render_png(parsed)
    img.save(OUTPUT_FILE)
    print(f"Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
