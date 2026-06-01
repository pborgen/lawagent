"""Fill the CT CCSG-1 (a.k.a. fm220.pdf) Child Support Guidelines worksheet.

The official form is an XFA form — its widgets won't accept normal
`widget.field_value = "..."` writes in a way that renders in all viewers.
This script does a "visual overlay": it reads each widget's bounding box
and writes plain text into the page content stream at the right position.
Result: a flat-looking PDF that prints / exports identically to a
hand-filled form.

Run:
    python -m ccsg1.fill

Input  : data/case/drafts/fm220_blank.pdf    (blank template; auto-created
                                              from data/case/drafts/fm220.pdf
                                              the first time you run this)
Output : data/case/drafts/fm220.pdf          (overwritten with the fill)

Values are hardcoded for Paul Borgen's current actual income (UI only).
Edit the VALUES section to update.
"""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

import pymupdf

# apps/ccsg1/fill.py → parents[2] is the repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DRAFTS = _REPO_ROOT / "data" / "case" / "drafts"
_SRC = _DRAFTS / "fm220.pdf"
_BLANK = _DRAFTS / "fm220_blank.pdf"


# ── VALUES ──────────────────────────────────────────────────────────────
PARENT_A_NAME = "Melanie Adams-Borgen"
PARENT_B_NAME = "Paul A. Borgen"
# Custody is joint physical custody per Proposed Order § 2(b). On the
# CCSG-1, joint custody is expressed by checking CheckBox1[2] (OTHER)
# and writing both names in the CUSTODIAN field. The baseline math
# below is unchanged; the shared-physical-custody deviation is applied
# in Section VIII (hand-marked).
CUSTODIAN_NAME = "Joint — Paul A. Borgen / Melanie Adams-Borgen"
CUSTODIAN_CHECKBOX = "CheckBox1[2]"  # was CheckBox1[1] for sole=Parent B
COURT = "Hartford J.D., 90 Washington St., Hartford, CT"
CASE_NO = "HHD-FA25-5089318-S"
N_CHILDREN = "2"
TODAY = datetime.date.today().strftime("%m/%d/%Y")

KIDS = [
    ("Anthony Borgen", "5/26/2013"),
    ("Natalie G. Borgen", "8/10/2021"),
]

# Section I — Net Income (weekly).
# Order: (NumericField1 index for Parent A, value, Parent B index, value).
# A-column rect is x0≈466, B-column rect is x0≈538.
SECTION_I_ROWS = [
    # Line  A_idx  A_val  B_idx  B_val
    ("1",     0,   "860",     1,  "721"),  # Gross income
    ("1a",   50,    "33",    51,    "0"),  # Hours/week
    ("2",     2,   "-56",     3,    "0"),  # Federal tax (Mel has credit)
    ("3",     4,    "53",     5,    "0"),  # SS / mandatory retirement
    ("4",     6,    "12",     7,    "0"),  # Medicare
    ("5",     8,    "16",     9,    "0"),  # State / local income tax
    ("6",    10,   "102",    11,    "0"),  # Medical/dental premiums
    ("7",    12,     "0",    13,    "0"),  # Court-ordered life ins.
    ("8",    14,     "0",    15,    "0"),  # Court-ordered disability
    ("9",    16,     "0",    17,    "0"),  # Mandatory union dues
    ("10",   18,     "0",    19,    "0"),  # Mandatory uniforms/tools
    ("11",   20,     "0",    21,    "0"),  # Alimony/CS for OTHER children
    ("12",   22,     "0",    23,    "0"),  # Qualified-child deduction
    ("13",   36,   "127",    38,    "0"),  # Sum lines 2-12
    ("14",   37,   "733",    39,  "721"),  # Net weekly income
]

# Section II — Current Support (page 1, single cells)
# Line 20 is computed mechanically per parent (Line 18 - Line 19) regardless
# of who is custodial — both columns get filled. Line 30 (page 2) is where
# the NCP's amount lands; under joint custody Line 30 = $0 (no NCP).
PAGE1_SINGLE = {
    40: "1450",    # Line 15 combined net weekly (rounded to nearest $10)
    41:  "404",    # Line 16 basic obligation (Schedule, 2 kids @ $1,450)
    42: "50.55",   # Line 17 Mel %  (= 733 / 1450, 2 decimals)
    43: "49.45",   # Line 17 Paul % (= 100 - 50.55, so they sum to 100)
    44:  "204",    # Line 18 Mel share (50.55% × $404)
    45:  "200",    # Line 18 Paul share (49.45% × $404)
    46:    "0",    # Line 19 SS dependency adj — Mel
    47:    "0",    # Line 19 SS dependency adj — Paul
    48:  "204",    # Line 20 Mel mechanical (Line 18 - Line 19)
    49:  "200",    # Line 20 Paul mechanical
}

# Section III — Net Disposable Income (page 2).
# Under joint custody, Line 30 = $0 (no NCP-to-CP transfer), so Lines 21
# and 23 equal Line 14 for both parents, and the disposable split lands
# at ~50/50.
PAGE2_FILLS = {
    0: "733",    # Line 21 Mel  (= Line 14, since Line 30 = 0)
    1: "721",    # Line 21 Paul (= Line 14, since Line 30 = 0)
    2:   "0",    # Line 22 SS dependency adj
    3: "733",    # Line 23 Mel
    4: "721",    # Line 23 Paul
    5: "1454",   # Line 24 combined net disposable (733 + 721)
    6:  "50",    # Line 25 Mel %  (733/1454 = 50.41% → 50)
    7:  "50",    # Line 25 Paul % (= 100 - 50)
}


# ── helpers ─────────────────────────────────────────────────────────────
def _text_w(text: str, *, fontsize: float) -> float:
    """Width of `text` in `helv` at the given fontsize (PDF user units)."""
    return pymupdf.get_text_length(text, fontname="helv", fontsize=fontsize)


def _draw_text(page, rect, text, *, fontsize=10, align="right"):
    """Write text inside the bounding box of a widget rect.

    align:
      "left"   x = rect.x0 + 2
      "right"  x = rect.x1 - text_w - 2   (default — numeric fields)
      "center" centered horizontally
    """
    text = str(text)
    if not text:
        return
    if align == "left":
        x = rect.x0 + 2
    elif align == "center":
        x = (rect.x0 + rect.x1) / 2 - _text_w(text, fontsize=fontsize) / 2
    else:
        x = rect.x1 - _text_w(text, fontsize=fontsize) - 2
    y = rect.y1 - 3  # baseline near the bottom of the field
    page.insert_text((x, y), text, fontsize=fontsize, fontname="helv",
                     color=(0, 0, 0))


def _draw_check(page, rect):
    """Draw a black 'X' inside a checkbox rect."""
    page.draw_line(rect.tl, rect.br, color=(0, 0, 0), width=1.4)
    page.draw_line(pymupdf.Point(rect.x0, rect.y1),
                   pymupdf.Point(rect.x1, rect.y0),
                   color=(0, 0, 0), width=1.4)


def _widgets_by_tail(page) -> dict[str, "pymupdf.Widget"]:
    """Index widgets on a page by the trailing path segment of field_name."""
    out: dict[str, pymupdf.Widget] = {}
    for w in page.widgets() or []:
        tail = w.field_name.split(".")[-1]
        out.setdefault(tail, w)  # first wins on duplicates
    return out


# ── main ────────────────────────────────────────────────────────────────
def main() -> None:
    if not _BLANK.exists():
        if not _SRC.exists():
            raise SystemExit(f"Neither {_SRC.name} nor {_BLANK.name} found.")
        shutil.copy2(_SRC, _BLANK)
        print(f"Preserved blank template → {_BLANK.name}")

    # Always start from the blank, so re-running gives a clean fill.
    shutil.copy2(_BLANK, _SRC)
    doc = pymupdf.open(_SRC)

    # ── Page 1 ─────────────────────────────────────────────────────────
    p1 = doc[0]
    w1 = _widgets_by_tail(p1)

    # Header
    header = {
        "PARENTA[0]":     PARENT_A_NAME,
        "PARENTB[0]":     PARENT_B_NAME,
        "CUSTODIAN[0]":   CUSTODIAN_NAME,
        "COURT[0]":       COURT,
        "CASENUMBER[0]":  CASE_NO,
        "CHILDNUMBER[0]": N_CHILDREN,
        "CHILD1[0]":      KIDS[0][0],
        "DOB1[0]":        KIDS[0][1],
        "CHILD2[0]":      KIDS[1][0],
        "DOB2[0]":        KIDS[1][1],
    }
    for name, value in header.items():
        w = w1.get(name)
        if w is None:
            print(f"  ! missing header field: {name}")
            continue
        _draw_text(p1, w.rect, value, fontsize=10, align="left")

    # Custodian flag — CheckBox1[0]=ParentA, [1]=ParentB, [2]=Other
    chk = w1.get(CUSTODIAN_CHECKBOX)
    if chk is not None:
        _draw_check(p1, chk.rect)

    # Section I rows
    for _line, a_idx, a_val, b_idx, b_val in SECTION_I_ROWS:
        for idx, val in ((a_idx, a_val), (b_idx, b_val)):
            w = w1.get(f"NumericField1[{idx}]")
            if w is None:
                print(f"  ! missing Sec I field: NumericField1[{idx}]")
                continue
            _draw_text(p1, w.rect, val, fontsize=10, align="right")

    # Section II single fields
    for idx, val in PAGE1_SINGLE.items():
        w = w1.get(f"NumericField1[{idx}]")
        if w is None:
            print(f"  ! missing Sec II field: NumericField1[{idx}]")
            continue
        _draw_text(p1, w.rect, val, fontsize=10, align="right")

    # ── Page 2 ─────────────────────────────────────────────────────────
    p2 = doc[1]
    w2 = _widgets_by_tail(p2)

    for idx, val in PAGE2_FILLS.items():
        w = w2.get(f"NumericField1[{idx}]")
        if w is None:
            print(f"  ! missing page-2 field: NumericField1[{idx}]")
            continue
        _draw_text(p2, w.rect, val, fontsize=10, align="right")

    # Footer signature line (PREPAREDBY / TITLE / DATE appear twice on the
    # form). Fill every occurrence.
    for w in p2.widgets() or []:
        tail = w.field_name.split(".")[-1]
        if tail == "PREPAREDBY[0]":
            _draw_text(p2, w.rect, PARENT_B_NAME, fontsize=10, align="left")
        elif tail == "TITLE[0]":
            _draw_text(p2, w.rect, "Self-Represented Party", fontsize=10,
                       align="left")
        elif tail == "DATE[0]":
            _draw_text(p2, w.rect, TODAY, fontsize=10, align="left")

    # Save (pymupdf can't overwrite an open document directly).
    tmp = _SRC.with_suffix(".pdf.tmp")
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    tmp.replace(_SRC)
    print(f"✓ Filled CCSG-1 → {_SRC}")
    print(f"  Blank template at  {_BLANK.name}")


if __name__ == "__main__":
    main()
