"""Self-contained Unicode exports; never interpret narrative as markup."""

import csv
import io
import unicodedata
from pathlib import Path

from fastapi import HTTPException

FONTS = Path(__file__).with_name("report_fonts")


def safe_cell(value):
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def csv_document(report):
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    def row(*values):
        writer.writerow([safe_cell(value) for value in values])

    snapshot = report["snapshot"]
    row("Weekly report", report["code"], report["status"], "Asia/Karachi")
    row("Period start inclusive", report["week_start"], "Period end exclusive", report["week_end"])
    row("Revision", report["revision_number"], "Submitted at", report["submitted_at"])
    row("Snapshot basis", snapshot_label(report))
    if report.get("preview_unavailable"):
        row("Preview unavailable", report["preview_unavailable_reason"])
    row(
        "Collection total PKR",
        snapshot["collection_total"],
        "Collection count",
        snapshot["collection_count"],
    )
    row("Transfer total PKR (all statuses)", snapshot["transfer_total"])
    for status, amount in snapshot["transfer_status_totals"].items():
        row("Transfer status as of snapshot", status, amount)
    row("Discrepancy detected", report["discrepancy"])
    row("Narrative", report["narrative"])
    row(
        "Kind",
        "ID",
        "Code",
        "Revision",
        "Business date",
        "Amount PKR",
        "Status / Collector",
        "Reference",
        "Notes",
    )
    for item in snapshot["collections"]:
        row(
            "Collection",
            item["id"],
            item["code"],
            item["version"],
            item["collected_on"],
            item["amount"],
            item["collector_name"],
            "",
            item["notes"],
        )
    for item in snapshot["transfers"]:
        row(
            "Transfer",
            item["id"],
            item["code"],
            item["version"],
            item["transferred_on"],
            item["amount"],
            item["status"],
            item["reference"],
            item["notes"],
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def snapshot_label(report):
    if report.get("snapshot_basis") == "last_submission":
        return "Last submitted figures - live preview unavailable"
    return (
        "Live draft preview"
        if report["status"] in {"Draft", "Returned"}
        else "Frozen submitted figures"
    )


def pdf_document(report):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("Noto", fname=str(FONTS / "NotoSans-Regular.ttf"))
    pdf.add_font("Arabic", fname=str(FONTS / "NotoNaskhArabic-Regular.ttf"))
    pdf.set_fallback_fonts(["Arabic"])
    pdf.set_text_shaping(True)
    pdf.set_title(str(report["code"]))
    pdf.set_author("Office Management Platform")
    pdf.add_page()

    def line(text, size=10):
        text = str(text).replace("\t", "    ").replace("\r", "")
        # Fail honestly on unsupported characters rather than silently dropping glyphs.
        for character in text:
            if character == "\n" or unicodedata.category(character) == "Cf":
                continue
            if not any(ord(character) in font.cmap for font in pdf.fonts.values()):
                raise HTTPException(
                    422,
                    "The PDF fonts cannot render a character in this report. "
                    "Use the UTF-8 CSV export.",
                )
        pdf.set_font("Noto", size=size)
        pdf.multi_cell(
            0, 7 if size >= 13 else 5.5, text, new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR"
        )

    snapshot = report["snapshot"]
    line("Weekly branch report", 18)
    line(report["code"], 11)
    branch = report["branch"]
    line(f"{branch.name} / {branch.code}")
    line(f"{report['week_start']} to {report['week_end']} (end exclusive), Asia/Karachi")
    line(f"Status: {report['status']} / submission revision {report['revision_number']}")
    if report.get("preview_unavailable"):
        line(snapshot_label(report), 12)
        line(report["preview_unavailable_reason"])
    elif report["status"] in {"Draft", "Returned"}:
        line("DRAFT PREVIEW - live figures; not submitted or approved", 12)
    else:
        line(f"Frozen submission: {report['submitted_at']}")
    if report["discrepancy"]:
        line("Ledger changes detected. Frozen figures below remain unchanged.", 12)
    line(
        f"Collections: PKR {snapshot['collection_total']} / {snapshot['collection_count']} entries",
        13,
    )
    line(
        f"Transfers, all statuses: PKR {snapshot['transfer_total']} / "
        f"{snapshot['transfer_count']} entries"
    )
    for status, amount in snapshot["transfer_status_totals"].items():
        line(f"{status}: PKR {amount}")
    line(
        "Transfer statuses reflect the snapshot time, not historical week-end receipt. "
        "These period totals are not cumulative outstanding balances."
    )
    line("Branch narrative", 13)
    line(report["narrative"] or "No narrative supplied.")
    line("Collection source revisions", 13)
    for item in snapshot["collections"]:
        line(
            f"{item['code']} / revision {item['version']} / {item['collected_on']} / "
            f"PKR {item['amount']}"
        )
        line(f"ID: {item['id']} / {item['collector_name']} / {item['notes']}")
    line("Transfer source revisions", 13)
    for item in snapshot["transfers"]:
        line(
            f"{item['code']} / revision {item['version']} / {item['transferred_on']} / "
            f"PKR {item['amount']} / {item['status']}"
        )
        line(f"ID: {item['id']} / {item['reference']} / {item['notes']}")
    return bytes(pdf.output())
