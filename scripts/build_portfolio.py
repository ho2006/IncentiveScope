"""Publish the authored English case as portable HTML and an optional PDF.

The small Markdown subset below covers this repository's report only. PDF export
uses optional authoring tools; it is not part of the analysis dependency chain.
"""

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/portfolio-report.md"
OUTPUT = ROOT / "reports/gmx-stip/portfolio"
REPO = "https://github.com/ho2006/IncentiveScope/blob/main/"


def target(value):
    if value.startswith(("https://", "http://", "#")):
        return value
    return urljoin(REPO + "docs/", value.lstrip("/") if not value.startswith("/") else "../" + value.lstrip("/"))


def inline(text, pdf=False):
    parts = []
    pattern = r"(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))"
    for token in re.split(pattern, text):
        if token.startswith("`"):
            value = html.escape(token[1:-1])
            parts.append(f'<font name="Scope">{value}</font>' if pdf else f"<code>{value}</code>")
        elif token.startswith("**"):
            parts.append(f"<b>{html.escape(token[2:-2])}</b>")
        elif token.startswith("["):
            label, url = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", token).groups()
            parts.append(f'<a href="{html.escape(target(url), quote=True)}">{html.escape(label)}</a>')
        else:
            parts.append(html.escape(token))
    return "".join(parts)


def blocks(text):
    """Read the authored headings, paragraphs, tables, lists and figures."""
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.splitlines()
        if match := re.fullmatch(r"(#{1,3}) (.+)", block):
            yield "heading", (len(match[1]), match[2])
        elif match := re.fullmatch(r"!\[([^\]]+)\]\(([^)]+)\)", block):
            yield "image", match.groups()
        elif all(line.startswith("|") for line in lines):
            yield "table", [[cell.strip() for cell in line.strip("|").split("|")] for line in lines if not re.fullmatch(r"[| :\-]+", line)]
        elif all(line.startswith("- ") for line in lines):
            yield "list", [line[2:] for line in lines]
        else:
            yield "paragraph", " ".join(lines)


def image_path(url):
    path = (ROOT / url.lstrip("/")).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"Missing report figure: {url}")
    return path


def render_html(content):
    sections, toc = [], []
    for kind, value in content:
        if kind == "heading":
            level, text = value
            slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            sections.append(f'<h{level} id="{slug}">{inline(text)}</h{level}>')
            if level == 2:
                toc.append(f'<a href="#{slug}">{html.escape(text)}</a>')
        elif kind == "paragraph":
            sections.append(f"<p>{inline(value)}</p>")
        elif kind == "list":
            sections.append("<ul>" + "".join(f"<li>{inline(row)}</li>" for row in value) + "</ul>")
        elif kind == "image":
            alt, url = value
            image_path(url)
            src = "../" + url.removeprefix("/reports/gmx-stip/")
            sections.append(f'<figure><img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}"><figcaption>{html.escape(alt)}</figcaption></figure>')
        elif kind == "table":
            rows = ["<tr>" + "".join(f"<{tag}>{inline(cell)}</{tag}>" for cell in row) + "</tr>" for tag, row in [("th", value[0]), *[("td", row) for row in value[1:]]]]
            sections.append('<div class="table"><table><thead>' + rows[0] + "</thead><tbody>" + "".join(rows[1:]) + "</tbody></table></div>")
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="A reproducible GMX incentive research case: protocol-event audits, fixed-cohort participation and a time-held-out PyTorch benchmark.">
<title>IncentiveScope | English research portfolio</title><style>
:root{--ink:#17333c;--muted:#566c74;--teal:#137e80;--line:#d8e2df}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:var(--ink);background:#f7f8f3;font:16px/1.7 system-ui,sans-serif}a{color:var(--teal);text-underline-offset:3px}header,main,footer{max-width:1000px;margin:auto;padding:24px}header{padding-top:42px}.brand{font-size:12px;font-weight:750;letter-spacing:.12em}nav{display:flex;flex-wrap:wrap;gap:12px 22px;margin:20px 0}.intro{color:var(--muted)}article{background:#fff;border:1px solid var(--line);padding:36px 48px;border-radius:12px}h1{font-size:clamp(29px,4vw,44px);line-height:1.16;letter-spacing:-.025em;margin:8px 0 32px}h2{font-size:24px;line-height:1.3;margin:44px 0 18px;scroll-margin-top:20px}h2:first-of-type{margin-top:20px}p{margin:16px 0}.table{overflow:auto;margin:24px 0}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.5}td,th{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left}th{background:#eff5f2}figure{margin:30px 0;overflow:auto}img{display:block;width:100%;height:auto;min-width:500px}figcaption{font-size:13px;color:var(--muted);margin-top:8px}code{overflow-wrap:anywhere;font-size:.88em;background:#edf3ee;padding:2px 4px}.toc{margin:0 0 28px;padding:16px 20px;background:#eff5f2;border-radius:8px}.toc div{display:grid;gap:8px;margin-top:12px;font-size:14px}summary{cursor:pointer;font-weight:650}:focus-visible{outline:3px solid #c68e37;outline-offset:4px}footer{font-size:13px;color:var(--muted)}
@media(max-width:650px){header,main,footer{padding:18px}article{padding:20px;border-radius:8px}h2{font-size:21px}img{min-width:540px}}
@media print{body{background:#fff;font-size:10pt}header,.toc,footer{display:none}main,article{padding:0;border:0;max-width:none}h1{font-size:25pt}h2{font-size:15pt;break-after:avoid}figure,table{break-inside:avoid}img{min-width:0}a{color:inherit}p{orphans:3;widows:3}}
</style></head><body><header><div class="brand">INCENTIVESCOPE / ENGLISH RESEARCH PORTFOLIO</div><p class="intro">Historical GMX V2 case · Arbitrum · observations from 2023–2024</p><nav><a href="../index.html">Explore participation</a><a href="../ml/index.html">Explore prediction</a><a href="research.pdf">Download English PDF</a><a href="https://github.com/ho2006/IncentiveScope">Source repository</a><a href="https://github.com/ho2006/IncentiveScope/blob/main/docs/reproduction.md">Reproduction runbook</a></nav></header><main><details class="toc"><summary>Jump to a section</summary><div>$TOC$</div></details><article>$BODY$</article></main><footer>Frozen event-time research. Counts describe addresses; associations do not identify causal incentive effects. Authored source and measurement evidence remain publicly inspectable.</footer></body></html>'''
    return page.replace("$TOC$", "".join(toc)).replace("$BODY$", "\n".join(sections))


def render_pdf(content, destination):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

    # Windows authoring font is embedded, making the exported PDF portable.
    pdfmetrics.registerFont(TTFont("Scope", "C:/Windows/Fonts/segoeui.ttf"))
    pdfmetrics.registerFont(TTFont("ScopeBold", "C:/Windows/Fonts/segoeuib.ttf"))
    pdfmetrics.registerFontFamily("Scope", normal="Scope", bold="ScopeBold")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("ScopeBody", fontName="Scope", fontSize=9.5, leading=14, spaceAfter=9, textColor=colors.HexColor("#17333c")))
    styles.add(ParagraphStyle("ScopeCell", parent=styles["ScopeBody"], fontSize=8, leading=11, spaceAfter=0))
    styles.add(ParagraphStyle("ScopeH1", parent=styles["ScopeBody"], fontName="ScopeBold", fontSize=23, leading=28, spaceAfter=19))
    styles.add(ParagraphStyle("ScopeH2", parent=styles["ScopeBody"], fontName="ScopeBold", fontSize=14, leading=18, spaceBefore=14, spaceAfter=9, keepWithNext=True))
    styles.add(ParagraphStyle("ScopeCaption", parent=styles["ScopeCell"], textColor=colors.HexColor("#566c74"), spaceAfter=12))
    doc = SimpleDocTemplate(str(destination), pagesize=(595.28, 841.89), leftMargin=46, rightMargin=46, topMargin=44, bottomMargin=44, title="IncentiveScope: participation after trading rebates end", author="IncentiveScope / ho2006")
    story = [Paragraph('INCENTIVESCOPE / ENGLISH RESEARCH PORTFOLIO', styles["ScopeCaption"])]
    for kind, value in content:
        if kind == "heading":
            level, text = value
            story.append(Paragraph(inline(text, pdf=True), styles["ScopeH1" if level == 1 else "ScopeH2"]))
        elif kind == "paragraph":
            story.append(Paragraph(inline(value, pdf=True), styles["ScopeBody"]))
        elif kind == "list":
            story.extend(Paragraph("• " + inline(row, pdf=True), styles["ScopeBody"]) for row in value)
        elif kind == "table":
            cells = [[Paragraph(inline(cell, pdf=True), styles["ScopeCell"]) for cell in row] for row in value]
            table = Table(cells, colWidths=[doc.width / len(cells[0])] * len(cells[0]), repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf3ee")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8e2df"))]))
            story.extend([KeepTogether([table]), Spacer(1, 12)])
        elif kind == "image":
            alt, url = value
            path = image_path(url)
            if path.suffix == ".svg":
                # The descriptive chart is vector; the ML renderer supplies PNG siblings.
                if path.with_suffix(".png").exists():
                    path = path.with_suffix(".png")
                else:
                    from svglib.svglib import svg2rlg
                    drawing = svg2rlg(str(path))
                    scale = doc.width / drawing.width
                    drawing.scale(scale, scale)
                    drawing.width *= scale
                    drawing.height *= scale
                    story.append(KeepTogether([drawing, Paragraph(html.escape(alt), styles["ScopeCaption"])]))
                    continue
            width, height = ImageReader(str(path)).getSize()
            story.append(KeepTogether([Image(str(path), width=doc.width, height=height * doc.width / width), Paragraph(html.escape(alt), styles["ScopeCaption"])]))
    def footer(canvas, document):
        canvas.setFont("Scope", 8)
        canvas.setFillColor(colors.HexColor("#566c74"))
        canvas.drawString(46, 24, "IncentiveScope | Historical observational research | ho2006.github.io/IncentiveScope/portfolio/")
        canvas.drawRightString(549, 24, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true", help="Optional ReportLab/svglib authoring export on Windows")
    args = parser.parse_args()
    content = list(blocks(SOURCE.read_text(encoding="utf-8")))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "index.html").write_text(render_html(content), encoding="utf-8", newline="\n")
    (OUTPUT / "research.md").write_bytes(SOURCE.read_bytes())
    if args.pdf:
        render_pdf(content, OUTPUT / "research.pdf")
    inputs = [SOURCE, ROOT / "reports/gmx-stip/results.json", ROOT / "reports/gmx-stip/ml/results.json"]
    receipt = {"source_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}, "files": [{"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in sorted(OUTPUT.iterdir()) if path.name != "manifest.json" and path.is_file()]}
    (OUTPUT / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Built English portfolio: {OUTPUT / 'index.html'}")


if __name__ == "__main__":
    main()
