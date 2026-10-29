"""Print stylesheet + table fitting for the Markdown → PDF export."""

import re

# The SME repo appends its diagram stylesheet here; the corp report has no
# diagrams, so that block is empty.
DIAGRAM_CSS = ""


WIDE_TABLE_COLUMNS = 7
EXTRA_WIDE_TABLE_COLUMNS = 9

_TABLE = re.compile(r"<table(?P<attrs>[^>]*)>(?P<body>.*?)</table>", re.DOTALL)
_CELL = re.compile(r"<t[hd]\b")
_ROW = re.compile(r"<tr\b.*?</tr>", re.DOTALL)

# [Sửa 29/10] Report font: Helvetica, headings 11pt, body and tables 10pt. Change these to resize.
# The business-model diagram and debt chart keep their own size and font (they are images).
FONT_FAMILY = 'Helvetica, Arial, "Liberation Sans", sans-serif'
HEADING_PT = 11
BODY_PT = 10

REPORT_CSS = f"""
@page {{
    size: A4;
    margin: 11mm 9mm 13mm 9mm;
    @bottom-center {{
        content: counter(page) " / " counter(pages);
        /* A page margin box does not inherit from body, so without this the page
           number printed in whatever the renderer defaults to. */
        font-family: {FONT_FAMILY};
        font-size: 8pt;
        color: #666;
    }}
}}
body {{
    /* Named in full so WeasyPrint asks fontconfig for the real face; Arial / Liberation Sans
       stand in where Helvetica is not installed (Linux, Databricks). */
    font-family: {FONT_FAMILY};
    font-size: {BODY_PT}pt;
    line-height: 1.4;
    margin: 0;
}}
h1, h2, h3, h4 {{ font-size: {HEADING_PT}pt; margin: 8px 0 4px; }}
p, li {{ margin: 4px 0; }}
blockquote {{
    margin: 6px 0; padding: 4px 10px;
    border-left: 3px solid #2f6f9f; background: #f5f8fb;
}}
code {{ font-size: {BODY_PT}pt; }}

table {{
    border-collapse: collapse;
    width: 100%;
    margin: 6px 0;
    font-size: {BODY_PT}pt;
    /* Let the engine fit columns to content instead of overflowing the page. */
    table-layout: auto;
    page-break-inside: auto;
}}
th, td {{
    border: 1px solid #999;
    padding: 3px 5px;
    vertical-align: top;
    overflow-wrap: break-word;
    /* [Sửa 29/10] no "word-break: break-word": at 10pt it split numbers ("92.92 / 1") */
}}
th {{ background: #eef2f6; text-align: left; }}
tr {{ page-break-inside: avoid; }}
thead {{ display: table-header-group; }}

/* [BRD 29/10] Mục 4: debt table on the left, monthly chart on the right, no outer border. */
table.layout {{ border: none; margin: 6px 0; }}
table.layout > tbody > tr > td, table.layout > tr > td {{ border: none; padding: 0 6px 0 0; vertical-align: top; }}
td.layout-main {{ width: 58%; }}
td.layout-side {{ width: 42%; }}

/* Wide financial tables step down instead of overflowing the page box. */
table.tbl-wide {{ font-size: 7.5pt; }}
table.tbl-wide th, table.tbl-wide td {{ padding: 2px 3px; }}
table.tbl-xwide {{ font-size: 6.8pt; }}
table.tbl-xwide th, table.tbl-xwide td {{ padding: 2px; letter-spacing: -0.1px; }}

/* Source citations. Class names are markdown's own (extensions=["footnotes"]),
   not ours. The marker stays small and unobtrusive so a cited sentence still
   reads as a sentence; the list at the end drops a size, as a reference
   apparatus rather than body text. */
sup a.footnote-ref {{ font-size: 7pt; text-decoration: none; color: #2f6f9f; }}
.footnote {{
    font-size: 8pt; color: #333; page-break-inside: auto;
    /* The margin the <hr> used to carry, kept now that it is gone so the block
       does not ride up against the last line of the report. */
    margin-top: 10px;
}}
/* markdown's footnotes extension opens the block with its own <hr>. The
   footnotes are already set apart by size, colour and position, so the rule was
   a second divider doing the same job. Hidden rather than restyled — the
   extension emits it either way, and display:none is honoured here: the PDF
   comes back with zero drawings on the page. */
.footnote hr {{ display: none; }}
.footnote ol {{ margin: 0 0 0 16px; padding: 0; }}
.footnote li {{ margin: 1px 0; page-break-inside: avoid; }}
.footnote li p {{ margin: 0; }}
a.footnote-backref {{ text-decoration: none; margin-left: 4px; }}
{DIAGRAM_CSS}
"""


def _column_count(table_body: str) -> int:
    """Widest row in the table, in cells."""

    rows = _ROW.findall(table_body)
    if not rows:
        return 0
    return max(len(_CELL.findall(row)) for row in rows)


def tag_wide_tables(html: str) -> str:
    """Add a width class to each table so the stylesheet can shrink wide ones."""

    def replace(match: re.Match[str]) -> str:
        columns = _column_count(match.group("body"))
        if columns >= EXTRA_WIDE_TABLE_COLUMNS:
            css_class = "tbl-xwide"
        elif columns >= WIDE_TABLE_COLUMNS:
            css_class = "tbl-wide"
        else:
            return match.group(0)
        attrs = match.group("attrs")
        if 'class="' in attrs:
            attrs = attrs.replace('class="', f'class="{css_class} ', 1)
        else:
            attrs = f'{attrs} class="{css_class}"'
        return f"<table{attrs}>{match.group('body')}</table>"

    return _TABLE.sub(replace, html or "")
