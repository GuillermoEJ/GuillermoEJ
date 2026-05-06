import os
import re
import subprocess
import sys
from pathlib import Path

OUTPUT_FILE = Path("bonsai.svg")

WIDTH = 60
HEIGHT = 20
FONT_SIZE = 14
CHAR_WIDTH = 8.4
LINE_HEIGHT = 18
BG_COLOR = "#0d1117"
DEFAULT_COLOR = "#c9d1d9"


def generate_raw_bonsai() -> str:
    cmd = [
        sys.executable, "-m", "pybonsai",
        "-i", "-b",
        "-x", str(WIDTH),
        "-y", str(HEIGHT),
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        cmd, check=True, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return result.stdout.decode("utf-8", errors="replace")


def parse_ansi_to_spans(raw: str) -> list[list[tuple[str, str]]]:
    raw = re.sub(r"\x1b\[\?[0-9]*[a-zA-Z]", "", raw)
    raw = re.sub(r"\x1b\[[0-9]*[A-HJ-Z]", "", raw)
    raw = re.sub(r"\x1b\[[0-9]*G", "", raw)
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
                    r, g, b = parts[2], parts[3], parts[4]
                    current_color = f"#{int(r):02x}{int(g):02x}{int(b):02x}"
            pos = match.end()

        if pos < len(line):
            spans.append((line[pos:], current_color))

        parsed_lines.append(spans)

    return parsed_lines


def filter_tree_lines(parsed_lines: list[list[tuple[str, str]]]) -> list[list[tuple[str, str]]]:
    filtered = []
    for spans in parsed_lines:
        plain = "".join(text for text, _ in spans)
        if "Saved tree to" in plain:
            continue
        filtered.append(spans)

    while filtered and all(t.strip() == "" for t, _ in filtered[-1]):
        filtered.pop()
    while filtered and all(t.strip() == "" for t, _ in filtered[0]):
        filtered.pop(0)

    min_indent = float("inf")
    for spans in filtered:
        plain = "".join(text for text, _ in spans)
        stripped = plain.lstrip(" ")
        if stripped:
            min_indent = min(min_indent, len(plain) - len(stripped))

    if min_indent == float("inf"):
        min_indent = 0

    trimmed = []
    for spans in filtered:
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


def escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def spans_to_svg(parsed_lines: list[list[tuple[str, str]]]) -> str:
    parsed_lines = filter_tree_lines(parsed_lines)

    content_width = max(
        sum(len(text) for text, _ in spans) for spans in parsed_lines
    ) if parsed_lines else 0

    svg_width = int(content_width * CHAR_WIDTH) + 20
    svg_height = int(len(parsed_lines) * LINE_HEIGHT) + 20

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}">',
        f'<rect width="100%" height="100%" fill="{BG_COLOR}"/>',
        f'<text font-family="monospace" font-size="{FONT_SIZE}" xml:space="preserve">',
    ]

    for i, spans in enumerate(parsed_lines):
        y = 10 + (i + 1) * LINE_HEIGHT
        parts.append(f'<tspan x="10" y="{y}">')
        for text, color in spans:
            escaped = escape_xml(text)
            if color == DEFAULT_COLOR:
                parts.append(escaped)
            else:
                parts.append(f'<tspan fill="{color}">{escaped}</tspan>')
        parts.append("</tspan>")

    parts.append("</text></svg>")
    return "\n".join(parts)


def main():
    raw = generate_raw_bonsai()
    parsed = parse_ansi_to_spans(raw)
    svg = spans_to_svg(parsed)
    OUTPUT_FILE.write_text(svg, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
