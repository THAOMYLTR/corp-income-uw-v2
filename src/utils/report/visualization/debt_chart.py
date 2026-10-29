"""[BRD 29/10] Chart beside the debt table (mục 4): dư nợ tại các TCTD theo từng tháng.

Input: the monthly balances OCR'd from CIC S10A, section 2.6 (cic_metrics → "monthly").
One series, so one hue and no legend: the title names it. Bars per month, a dashed line at
the 12-month average (the figure shown in the table), only the latest bar labelled.
Returned as a one-line <img> with the SVG inside (data URI), like the business-model diagram,
so it shows in the PDF, HTML and .md. Edit the constants below to restyle it.
"""

from __future__ import annotations

import base64
import html
import math

WIDTH, HEIGHT = 380, 230
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 46, 12, 30, 34
BAR = "#4f6bb0"            # the one series colour
INK, MUTED, GRID = "#1f1f3d", "#6b6b80", "#e3e3ea"
FONT = "Arial, Helvetica, sans-serif"


def _million(value: float) -> str:
    return f"{value / 1e6:,.0f}".replace(",", ".")


def _month_label(month: str) -> str:
    """'03/2026' → '03/26'."""
    parts = month.split("/")
    return f"{parts[0]}/{parts[1][-2:]}" if len(parts) == 2 else month


def _nice_step(top: float, ticks: int = 4) -> float:
    """A round grid step (1, 2, 2.5, 5 × 10^n) so the axis reads 0 / 25.000 / 50.000 …"""

    raw = top / ticks
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    return next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)


def debt_chart(monthly: list[tuple[str, float]], average: float | None = None) -> str:
    """'' when the CIC has no monthly balances."""

    if not monthly:
        return ""
    peak = max(max(v for _, v in monthly), average or 0) or 1.0
    step_value = _nice_step(peak)
    top = step_value * math.ceil(peak / step_value)
    plot_w, plot_h = WIDTH - PAD_LEFT - PAD_RIGHT, HEIGHT - PAD_TOP - PAD_BOTTOM
    step = plot_w / len(monthly)
    bar_w = max(4.0, step - 4)                     # 4px gap between bars
    y = lambda v: PAD_TOP + plot_h - v / top * plot_h
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
             f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{FONT}">',
             f'<rect width="100%" height="100%" fill="#ffffff"/>',
             f'<text x="{PAD_LEFT}" y="16" font-size="11" font-weight="bold" fill="{INK}">'
             f'Diễn biến dư nợ tại các TCTD (triệu VNĐ) — T{html.escape(_month_label(monthly[-1][0]))}: '
             f'{_million(monthly[-1][1])}</text>']
    for k in range(round(top / step_value) + 1):   # recessive grid + y labels
        value = step_value * k
        gy = y(value)
        parts.append(f'<line x1="{PAD_LEFT}" x2="{WIDTH - PAD_RIGHT}" y1="{gy:.1f}" y2="{gy:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{PAD_LEFT - 4}" y="{gy + 3:.1f}" text-anchor="end" font-size="9" '
                     f'fill="{MUTED}">{_million(value)}</text>')
    every = 1 if len(monthly) <= 8 else 2         # keep month labels from colliding
    for i, (month, value) in enumerate(monthly):
        x = PAD_LEFT + i * step + (step - bar_w) / 2
        parts.append(f'<rect x="{x:.1f}" y="{y(value):.1f}" width="{bar_w:.1f}" '
                     f'height="{PAD_TOP + plot_h - y(value):.1f}" rx="2" fill="{BAR}">'
                     f'<title>{html.escape(month)}: {_million(value)}</title></rect>')
        if i % every == 0 or i == len(monthly) - 1:
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{HEIGHT - PAD_BOTTOM + 13}" text-anchor="middle" '
                         f'font-size="9" fill="{MUTED}">{html.escape(_month_label(month))}</text>')
    if average:
        ay = y(average)
        parts.append(f'<line x1="{PAD_LEFT}" x2="{WIDTH - PAD_RIGHT}" y1="{ay:.1f}" y2="{ay:.1f}" '
                     f'stroke="{INK}" stroke-width="1" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="{PAD_LEFT + 4}" y="{ay - 4:.1f}" font-size="9" fill="{INK}">'
                     f'BQ 12 tháng: {_million(average)}</text>')
    parts.append(f'<line x1="{PAD_LEFT}" x2="{WIDTH - PAD_RIGHT}" y1="{PAD_TOP + plot_h}" '
                 f'y2="{PAD_TOP + plot_h}" stroke="{MUTED}" stroke-width="1"/></svg>')
    svg = "".join(parts)
    alt = html.escape("Dư nợ theo tháng: " + "; ".join(f"{m} {_million(v)}" for m, v in monthly))
    return (f'<img alt="{alt}" style="width:100%;max-width:{WIDTH}px" '
            f'src="data:image/svg+xml;base64,{base64.b64encode(svg.encode("utf-8")).decode("ascii")}">')
