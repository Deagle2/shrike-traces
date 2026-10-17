#!/usr/bin/env python3
"""Render a compact digital waveform SVG from a shrike-traces CSV capture."""

from __future__ import annotations

import argparse
import csv
from html import escape
from pathlib import Path


DEFAULT_SIGNALS = ("a", "b", "c", "d", "ab", "cd", "y", "triggered")


def digital_path(values: list[int], x0: int, step: int, y: int) -> str:
    high = y - 10
    low = y + 10
    points = [f"M {x0} {high if values[0] else low}"]
    for index, value in enumerate(values):
        left = x0 + index * step
        right = left + step
        level = high if value else low
        if index:
            previous = high if values[index - 1] else low
            points.append(f"L {left} {previous} L {left} {level}")
        points.append(f"L {right} {level}")
    return " ".join(points)


def render(
    input_path: Path,
    output_path: Path,
    title: str,
    signals: tuple[str, ...] = DEFAULT_SIGNALS,
    vector_field: str = "stimulus",
) -> None:
    with input_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("capture CSV is empty")

    missing = [name for name in signals if name not in rows[0]]
    if missing:
        raise ValueError("missing CSV signals: " + ", ".join(missing))

    x0, step = 150, 60
    width = x0 + len(rows) * step + 30
    height = 150 + len(signals) * 48
    trigger_index = next(
        (index for index, row in enumerate(rows) if int(row.get("trigger", "0"))),
        8,
    )

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        '<style>text{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;fill:#c9d1d9}.label{font-size:15px}.small{font-size:12px;fill:#8b949e}.wave{fill:none;stroke:#58a6ff;stroke-width:2}.derived{stroke:#3fb950}.grid{stroke:#21262d;stroke-width:1}.trigger{fill:#f8514922;stroke:#f85149;stroke-width:1}</style>',
        f'<text x="24" y="30" font-size="20" font-weight="700">{escape(title)}</text>',
        f'<text x="24" y="52" class="small">Physical Shrike Lite capture; trigger is the red column at sample {trigger_index}.</text>',
        f'<rect class="trigger" x="{x0 + trigger_index * step}" y="66" width="{step}" height="{height - 88}"/>',
    ]

    for index, row in enumerate(rows):
        x = x0 + index * step
        lines.append(f'<line class="grid" x1="{x}" y1="66" x2="{x}" y2="{height - 22}"/>')
        lines.append(f'<text class="small" x="{x + step / 2}" y="82" text-anchor="middle">{index}</text>')
        vector = row.get(vector_field, "")
        lines.append(f'<text class="small" x="{x + step / 2}" y="102" text-anchor="middle">{escape(vector)}</text>')
    lines.append(f'<text class="small" x="{x0 - 12}" y="102" text-anchor="end">vector</text>')

    for signal_index, name in enumerate(signals):
        y = 130 + signal_index * 48
        values = [int(row[name]) for row in rows]
        css_class = "wave derived" if name in {"ab", "cd", "y"} else "wave"
        lines.append(f'<text class="label" x="{x0 - 20}" y="{y + 5}" text-anchor="end">{escape(name)}</text>')
        lines.append(f'<path class="{css_class}" d="{digital_path(values, x0, step, y)}"/>')

    lines.append(f'<text class="small" x="24" y="{height - 14}">Source: {escape(input_path.as_posix())}</text>')
    lines.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="shrike-traces capture")
    parser.add_argument(
        "--signals",
        default=",".join(DEFAULT_SIGNALS),
        help="comma-separated CSV signal columns",
    )
    parser.add_argument(
        "--vector-field",
        default="stimulus",
        help="CSV column shown as the stimulus/vector label",
    )
    args = parser.parse_args()
    signals = tuple(name.strip() for name in args.signals.split(",") if name.strip())
    if not signals:
        parser.error("--signals must contain at least one column")
    render(args.input, args.output, args.title, signals, args.vector_field)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
