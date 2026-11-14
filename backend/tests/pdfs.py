"""Build results PDFs for tests: a statement laid out the way a company's filing is, so the extractor is
exercised end to end without any real filing in the repository."""
import textwrap

import pymupdf

DATES = ("30.09.2026", "30.06.2026", "30.09.2025")


def make_pdf(*, rotation=0, dates=DATES, unit="Rs. in crore", fiddle=None, title="STATEMENT OF UNAUDITED CONSOLIDATED FINANCIAL RESULTS FOR THE QUARTER AND HALF YEAR ENDED 30TH SEPTEMBER 2026", pbt=None):
    """A one-page results statement with six figure columns, built the way a company's PDF would be.
    With a rotation, the text is drawn sideways on the sheet and shown upright through /Rotate, which is how Tata Steel's filing is made.
    `pbt` overrides the three profit-before-tax figures (current, preceding, year ago)."""
    doc = pymupdf.open()
    sideways = rotation in (90, 270)
    page = doc.new_page(width=595 if sideways else 842, height=842 if sideways else 595)
    page.set_rotation(rotation)
    derotate = page.derotation_matrix  # where a point of the upright page sits on the sheet
    size = 8

    def left(x, y, text):
        page.insert_text(pymupdf.Point(x, y) * derotate, text, fontsize=size, rotate=rotation)

    def right(x, y, text):
        left(x - pymupdf.get_text_length(text, fontsize=size), y, text)

    left(40, 40, title)
    left(40, 54, f"({unit}, except per share data)")
    columns = [450, 510, 570, 630, 690, 750]
    for x, text in zip(columns, [*dates, "30.09.2026", "30.09.2025", "31.03.2026"]):
        right(x, 76, text)
    left(450, 66, "Quarter ended")
    table = {
        "Revenue from operations": [1000.0, 900.0, 800.0, 1900.0, 1500.0, 3200.0],
        "Other income": [50.0, 45.0, 40.0, 95.0, 80.0, 170.0],
        "Total income": [1050.0, 945.0, 840.0, 1995.0, 1580.0, 3370.0],
        "Total expenses": [850.0, 800.0, 700.0, 1650.0, 1300.0, 2800.0],
        "Profit before tax": [200.0, 145.0, 140.0, 345.0, 280.0, 570.0],
        "Tax expense": [50.0, 36.0, 35.0, 86.0, 70.0, 142.0],
        "Profit after tax": [150.0, 109.0, 105.0, 259.0, 210.0, 428.0],
    }
    if pbt:
        table["Profit before tax"][:3] = list(pbt)
    if fiddle:
        fiddle(table)
    y = 96
    for label, values in table.items():
        left(40, y, label)
        for x, v in zip(columns, values):
            right(x, y, f"{v:,.2f}")
        y += 14
    return doc.tobytes()


def make_plain_pdf(text="Annual general meeting notice"):
    """A PDF with no results statement in it."""
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def make_transcript_pdf(pages, *, header="Acme Ltd - Earnings Call"):
    """A transcript PDF from a list of page texts, each page with the repeated header and "Page n of N" a real one has."""
    doc = pymupdf.open()
    for number, text in enumerate(pages, start=1):
        page = doc.new_page(width=595, height=842)
        y = 40
        for raw in [header, f"Page {number} of {len(pages)}", ""] + text.split("\n"):
            for line in textwrap.wrap(raw, 95) or [""]:  # keep every line inside the page, so all of it is extracted
                page.insert_text((50, y), line, fontsize=9)
                y += 11
    return doc.tobytes()
