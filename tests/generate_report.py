#!/usr/bin/env python3
"""Builds a PDF test report (and a markdown summary) from report/results.json.

    python generate_report.py [--report-dir report]

Outputs: <report-dir>/test-report.pdf and <report-dir>/summary.md
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

GREEN = colors.HexColor("#1a9e5c")
RED = colors.HexColor("#d64545")
INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#6b7785")
LINE = colors.HexColor("#d9dee4")
SOFT_GREEN = colors.HexColor("#e6f6ee")
SOFT_RED = colors.HexColor("#fdecec")
SOFT_GREY = colors.HexColor("#f4f6f8")

PAGE_W, _ = A4
CONTENT_W = PAGE_W - 40 * mm

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=22, textColor=colors.white, leading=26)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=INK, spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9, leading=12, textColor=INK)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=7.5, leading=10)
MUTED_S = ParagraphStyle("MutedS", parent=SMALL, textColor=MUTED)
CELL_W = ParagraphStyle("CellW", parent=SMALL, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)


def clean(text):
    """The built-in PDF fonts lack a few characters (e.g. the unicode minus)."""
    return str(text).replace("−", "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def p(text, style=SMALL):
    return Paragraph(clean(text), style)


# ---- charts ---------------------------------------------------------------

def donut(passed, failed):
    d = Drawing(150 * mm, 55 * mm)
    d.hAlign = "LEFT"
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 10 * mm, 4 * mm, 46 * mm, 46 * mm
    data, cols, labels = [], [], []
    if passed:
        data.append(passed); cols.append(GREEN); labels.append("Passed")
    if failed:
        data.append(failed); cols.append(RED); labels.append("Failed")
    pie.data = data
    for i, c in enumerate(cols):
        pie.slices[i].fillColor = c
        pie.slices[i].strokeColor = colors.white
        pie.slices[i].strokeWidth = 2
    d.add(pie)
    total = passed + failed
    # White disc in the middle turns the pie into a donut with the pass rate inside.
    cx, cy = pie.x + pie.width / 2, pie.y + pie.height / 2
    from reportlab.graphics.shapes import Circle
    d.add(Circle(cx, cy, 15 * mm, fillColor=colors.white, strokeColor=colors.white))
    rate = (passed / total * 100) if total else 0
    d.add(String(cx, cy - 2, f"{rate:.0f}%", textAnchor="middle", fontSize=18, fontName="Helvetica-Bold", fillColor=INK))
    d.add(String(cx, cy - 11, "pass rate", textAnchor="middle", fontSize=7, fillColor=MUTED))
    # Legend
    y = 34 * mm
    for label, count, c in (("Passed", passed, GREEN), ("Failed", failed, RED)):
        d.add(Rect(70 * mm, y, 4 * mm, 4 * mm, fillColor=c, strokeColor=c))
        d.add(String(77 * mm, y + 0.6 * mm, f"{label}: {count}", fontSize=10, fillColor=INK))
        y -= 8 * mm
    return d


def duration_chart(results):
    d = Drawing(CONTENT_W, 62 * mm)
    d.hAlign = "LEFT"
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 14 * mm, 14 * mm, CONTENT_W - 20 * mm, 40 * mm
    ch.data = [[r["duration"] for r in results]]
    ch.categoryAxis.categoryNames = [r["id"] for r in results]
    ch.categoryAxis.labels.fontSize = 7
    ch.valueAxis.labels.fontSize = 7
    ch.valueAxis.valueMin = 0
    ch.valueAxis.valueStep = None
    ch.valueAxis.visibleGrid = True
    ch.valueAxis.gridStrokeColor = LINE
    ch.barWidth = 10
    ch.barLabelFormat = "%.1f"
    ch.barLabels.fontSize = 6.5
    ch.barLabels.nudge = 6
    for i, r in enumerate(results):
        ch.bars[(0, i)].fillColor = GREEN if r["status"] == "PASS" else RED
        ch.bars[(0, i)].strokeColor = None
    d.add(ch)
    d.add(String(2 * mm, 36 * mm, "seconds", fontSize=7, fillColor=MUTED, angle=90))
    return d


def progress_bar(passed, failed, width=CONTENT_W, height=5 * mm):
    d = Drawing(width, height)
    d.hAlign = "LEFT"
    total = max(passed + failed, 1)
    pw = width * passed / total
    if passed:
        d.add(Rect(0, 0, pw, height, fillColor=GREEN, strokeColor=None))
    if failed:
        d.add(Rect(pw, 0, width - pw, height, fillColor=RED, strokeColor=None))
    return d


# ---- layout helpers ------------------------------------------------------------

def kpi_tiles(items):
    """items: [(label, value, colour)] rendered as a row of coloured tiles."""
    w = CONTENT_W / len(items)
    cells = []
    for label, value, c in items:
        cells.append([Paragraph(f'<font size="20" color="{c.hexval().replace("0x", "#")}"><b>{value}</b></font><br/>', BODY),
                      Paragraph(label, MUTED_S)])
    t = Table([[Table([[c[0]], [c[1]]], colWidths=[w - 4 * mm]) for c in cells]], colWidths=[w] * len(items))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), SOFT_GREY), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def banner(text, sub, ok):
    t = Table([[Paragraph(clean(text), H1)], [Paragraph(clean(sub), ParagraphStyle("s", parent=SMALL, textColor=colors.white, fontSize=9))]],
              colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN if ok else RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
    ]))
    return t


def status_cell(status):
    return Paragraph(status, CELL_W)


def table(rows, widths, header=True, extra=()):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(style + list(extra)))
    return t


def hdr(*names):
    return [Paragraph(f"<b>{n}</b>", ParagraphStyle("h", parent=SMALL, textColor=colors.white)) for n in names]


def fmt_expected(case):
    parts = [("Lines", case["expected_lines"]), ("List", case["expected_list"]), ("Discount", case["expected_discount"]),
             ("Subtotal", case["expected_subtotal"]), ("SST", case["expected_sst"]), ("Total", case["expected_total"])]
    s = ", ".join(f"{k} {v}" for k, v in parts if v not in ("", None))
    if case["expected_notice"]:
        s += (", " if s else "") + f'Notice "{case["expected_notice"]}"'
    return s


def fmt_actual(actual):
    if not actual:
        return "no result captured"
    parts = [("Lines", actual["lines"]), ("List", actual["list"]), ("Discount", actual["discount"]),
             ("Subtotal", actual["subtotal"]), ("SST", actual["sst"]), ("Total", actual["total"])]
    s = ", ".join(f"{k} {v}" for k, v in parts if v not in ("", None))
    if actual["notice"]:
        s += (", " if s else "") + f'Notice "{actual["notice"]}"'
    return s


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 10 * mm, "AI Gateway - Selenium test report")
    canvas.drawRightString(PAGE_W - 20 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ---- main ----------------------------------------------------------------------

def build(report_dir):
    data = json.loads((report_dir / "results.json").read_text(encoding="utf-8"))
    results = data["results"]
    env = data["environment"]
    total = len(results)
    failed_list = [r for r in results if r["status"] == "FAIL"]
    passed = total - len(failed_list)
    failed = len(failed_list)
    ok = failed == 0
    pass_rate = passed / total * 100 if total else 0
    sum_time = sum(r["duration"] for r in results)
    avg = sum_time / total if total else 0
    slowest = max(results, key=lambda r: r["duration"]) if results else None
    fastest = min(results, key=lambda r: r["duration"]) if results else None
    started = datetime.fromisoformat(data["started"]).strftime("%d %b %Y, %H:%M:%S UTC")

    story = [
        banner("ALL TESTS PASSED" if ok else f"{failed} TEST{'S' if failed != 1 else ''} FAILED",
               f"AI Gateway usage calculator  |  {env['os']}  |  {started}", ok),
        Spacer(1, 8),
        kpi_tiles([("Total tests", total, INK), ("Passed", passed, GREEN), ("Failed", failed, RED if failed else MUTED),
                   ("Pass rate", f"{pass_rate:.0f}%", GREEN if ok else RED), ("Total time", f"{data['total_duration']:.1f}s", INK)]),
        Spacer(1, 6),
        progress_bar(passed, failed),
        KeepTogether([Paragraph("Results at a glance", H2), donut(passed, failed)]),
    ]

    # b) failed tests
    story.append(Paragraph("Failed test cases", H2))
    if not failed_list:
        t = Table([[Paragraph("No failures - every test case matched its expected result.", BODY)]], colWidths=[CONTENT_W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT_GREEN), ("BOX", (0, 0), (-1, -1), 0.5, GREEN),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        story.append(t)
    else:
        for r in failed_list:
            reasons = "<br/>".join("- " + clean(f) for f in r["failures"])
            box = Table([[Paragraph(f'<b>{r["id"]}</b> - {clean(r["description"])}', BODY)],
                         [Paragraph(f'<font color="#d64545"><b>Reason</b></font><br/>{reasons}', SMALL)],
                         [Paragraph(f'Expected: {clean(fmt_expected(r["case"]))}<br/>Actual: {clean(fmt_actual(r["actual"]))}', MUTED_S)]],
                        colWidths=[CONTENT_W])
            box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT_RED), ("BOX", (0, 0), (-1, -1), 0.8, RED),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
            story += [KeepTogether([box]), Spacer(1, 5)]

    # c) execution times
    story.append(KeepTogether([Paragraph("Execution times", H2), duration_chart(results)]))
    if results:
        story.append(Paragraph(
            f"Average <b>{avg:.2f}s</b> per test  |  slowest <b>{slowest['id']}</b> ({slowest['duration']:.2f}s)  |  "
            f"fastest <b>{fastest['id']}</b> ({fastest['duration']:.2f}s)  |  sum of tests {sum_time:.1f}s of {data['total_duration']:.1f}s wall time "
            f"(the rest is browser start-up and shutdown).", BODY))

    # all results table
    story.append(Paragraph("All test cases", H2))
    rows = [hdr("ID", "Description", "Status", "Time (s)", "Notes")]
    styles = []
    for i, r in enumerate(results, start=1):
        rows.append([p(r["id"]), p(r["description"]), status_cell(r["status"]), p(f'{r["duration"]:.2f}'),
                     p("; ".join(r["failures"]) if r["failures"] else "-")])
        styles.append(("BACKGROUND", (2, i), (2, i), GREEN if r["status"] == "PASS" else RED))
        if r["status"] == "FAIL":
            styles.append(("BACKGROUND", (0, i), (1, i), SOFT_RED))
            styles.append(("BACKGROUND", (3, i), (4, i), SOFT_RED))
    story.append(table(rows, [15 * mm, 68 * mm, 18 * mm, 16 * mm, CONTENT_W - 117 * mm], extra=styles))

    # e) expected vs actual
    story.append(Paragraph("Inputs, expected and actual values", H2))
    rows = [hdr("ID", "Inputs", "Expected", "Actual")]
    for r in results:
        c = r["case"]
        inputs = f'Batch {"on" if c["batch"].lower() == "true" else "off"}; ' + (c["usage"].replace(";", ", ").replace("=", " = ") or "no usage")
        if c["after_calculate"]:
            inputs += f'; then {c["after_calculate"]}'
        rows.append([p(r["id"]), p(inputs), p(fmt_expected(c)), p(fmt_actual(r["actual"]))])
    story.append(table(rows, [14 * mm, 42 * mm, (CONTENT_W - 56 * mm) / 2, (CONTENT_W - 56 * mm) / 2]))

    # environment
    story.append(Paragraph("Test environment", H2))
    ci = os.environ.get("GITHUB_RUN_ID")
    env_rows = [["Application URL", data["url"]], ["Operating system", env["os"]], ["Browser", env["browser"]
                + (" (headless)" if env["headless"] else "")], ["ChromeDriver", env["chromedriver"] or "-"],
                ["Python", env["python"]], ["Started", started]]
    if ci:
        repo, sha = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_SHA", "")[:7]
        env_rows += [["Repository", repo], ["Commit", sha], ["Workflow run", f"{os.environ.get('GITHUB_WORKFLOW', '')} #{os.environ.get('GITHUB_RUN_NUMBER', '')}"]]
    story.append(table([[p(k, MUTED_S), p(v)] for k, v in env_rows], [38 * mm, CONTENT_W - 38 * mm], header=False,
                       extra=[("BACKGROUND", (0, 0), (0, -1), SOFT_GREY)]))

    # screenshots
    shots = [r for r in results if r.get("screenshot") and (report_dir / r["screenshot"]).exists()]
    if shots:
        story.append(Paragraph("Screenshots (final page state of each test)", H2))
        w = (CONTENT_W - 6 * mm) / 2
        cells = []
        for r in shots:
            img = Image(str(report_dir / r["screenshot"]), width=w, height=w * 900 / 1280)
            border = GREEN if r["status"] == "PASS" else RED
            cell = Table([[Paragraph(f'<b>{r["id"]}</b>  {r["status"]}', SMALL)], [img]], colWidths=[w])
            cell.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, border), ("BACKGROUND", (0, 0), (0, 0), SOFT_GREEN if r["status"] == "PASS" else SOFT_RED)]))
            cells.append(cell)
        grid = [cells[i:i + 2] + [""] * (2 - len(cells[i:i + 2])) for i in range(0, len(cells), 2)]
        gt = Table(grid, colWidths=[w + 3 * mm, w + 3 * mm])
        gt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(gt)

    out = report_dir / "test-report.pdf"
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                      title="AI Gateway - Selenium test report", author="CI").build(story, onFirstPage=footer, onLaterPages=footer)

    # Markdown summary (shown on the workflow run page)
    md = [f"## {'✅' if ok else '❌'} Selenium tests: {passed}/{total} passed ({pass_rate:.0f}%)", "",
          "| Test | Status | Time (s) |", "|---|---|---|"]
    md += [f"| {r['id']} - {r['description']} | {'✅ PASS' if r['status'] == 'PASS' else '❌ FAIL'} | {r['duration']:.2f} |" for r in results]
    for r in failed_list:
        md += ["", f"**{r['id']}** failed: " + "; ".join(r["failures"])]
    md += ["", f"Total time {data['total_duration']:.1f}s on {env['os']}, {env['browser']}. Full PDF report is attached as a build artifact."]
    (report_dir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Report written to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", default=str(Path(__file__).with_name("report")))
    build(Path(ap.parse_args().report_dir))
