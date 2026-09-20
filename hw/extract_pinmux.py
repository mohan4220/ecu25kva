#!/usr/bin/env python3
"""Extract the S32K148 144-LQFP pin table from NXP's own spreadsheet.

WHY THIS SCRIPT EXISTS. docs/pinmap.md assigned 37 PTxx signals by reading
`S32K148_IO_Signal_Description_Input_Multiplexing.xlsx`, which is not a
download -- it is one of eleven workbooks EMBEDDED as file attachments
inside the S32K1xx Reference Manual PDF, and it is the only place the
per-pin package numbers exist. The datasheet says so itself (Rev. 15,
sec.10.1: "For package pinouts and signal descriptions, refer to the
Reference Manual"), and the Reference Manual's Chapter 4 in turn defers to
these attachments rather than inlining them.

That file was extracted once and then not kept, so pinmap.md cited a
source the repo no longer held and the symbol could not be built from it.
This script and the cached output beside it are the fix: the extraction is
reproducible, and refs/ now holds the workbook itself.

Stdlib only -- no openpyxl. An .xlsx is a zip of XML, and the two sheets
needed here are simple enough that depending on a package to read them
would be the larger cost.

Source, recorded so the chain is checkable:
  S32K1xx Series Reference Manual, Rev. 13, 04/2020
  https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/S32K/32215/1/S32K-RM.pdf
  attachment 8 of 11, extracted with `pdfdetach -save 8`
"""
import csv
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

PKG = "S32K148_144lqfp"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "refs",
                    "S32K148_IO_Signal_Description_Input_Multiplexing.xlsx")
OUT_PINS = os.path.join(ROOT, "refs", "s32k148-144lqfp-pins.csv")
OUT_ALT = os.path.join(ROOT, "refs", "s32k148-144lqfp-altfn.csv")


def open_book(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid = {r.get("Id"): r.get("Target")
           for r in rels.findall(RNS + "Relationship")}
    sheets = {}
    for s in wb.find(NS + "sheets"):
        t = rid[s.get(RID)].lstrip("/")
        sheets[s.get("name")] = t if t.startswith("xl/") else "xl/" + t
    return z, shared, sheets


def read_rows(z, shared, target):
    """Yield each row as {column letter: cell text}."""
    for row in ET.fromstring(z.read(target)).iter(NS + "row"):
        cells = {}
        for c in row.findall(NS + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v, isx = c.find(NS + "v"), c.find(NS + "is")
            if c.get("t") == "s" and v is not None:
                val = shared[int(v.text)]
            elif isx is not None:
                val = "".join(t.text or "" for t in isx.iter(NS + "t"))
            else:
                val = v.text if v is not None else ""
            cells[col] = (val or "").strip()
        yield cells


def header_map(row):
    return {v: k for k, v in row.items() if v}


def extract_io(z, shared, sheets):
    """Port pins from the 'IO Signal Table' sheet.

    Layout: each pin starts a block whose FIRST row carries the port name
    and the per-package pin numbers; the rows under it are that pin's
    alternate functions, one per MUX (SSS) value, with the port column
    blank. So column A is the block delimiter, and everything else on the
    first row is pin-level while the Function/Module columns are
    mux-level.
    """
    rows = list(read_rows(z, shared, sheets["IO Signal Table"]))
    hdr = None
    for r in rows[:6]:
        if r.get("A") == "Port":
            hdr = header_map(r)
            break
    if hdr is None:
        sys.exit("IO Signal Table: header row not found")
    for need in ("Port", PKG, "Function", "PE", "PS", "Pad Type", "MUX[2:0]"):
        if need not in hdr:
            sys.exit(f"IO Signal Table: column {need!r} not found")

    pins, alts, cur = [], [], None
    for r in rows:
        if r.get(hdr["Port"], "").startswith("PT"):
            num = r.get(hdr[PKG], "")
            cur = {
                "pin": num,
                "port": r[hdr["Port"]],
                "pad_type": r.get(hdr["Pad Type"], ""),
                "pe": r.get(hdr["PE"], ""),
                "ps": r.get(hdr["PS"], ""),
            }
            # A blank cell OR a literal "-" means this port is not bonded
            # out on this package -- NXP uses both. Keep it out of the
            # symbol rather than guessing. The duplicate-pin guard below
            # is what caught the "-" spelling: 28 ports collided on a
            # single "pin" named "-".
            if num and num != "-":
                pins.append(cur)
            else:
                cur = None
            continue
        if cur is None:
            continue
        fn = r.get(hdr["Function"], "")
        if fn and fn != "DISABLED":
            alts.append({"pin": cur["pin"], "port": cur["port"],
                         "mux": r.get(hdr["SSS"] if "SSS" in hdr else "C", ""),
                         "function": fn,
                         "module": r.get(hdr["Module"], ""),
                         "direction": r.get(hdr["Direction"], "")})
    return pins, alts


def extract_supplies(z, shared, sheets):
    """Power/ground pins. One net spans several rows; column A carries the
    net name only on the first of them, so it forward-fills."""
    rows = list(read_rows(z, shared, sheets["Supplies"]))
    hdr = header_map(rows[0])
    for need in ("Package Net", PKG):
        if need not in hdr:
            sys.exit(f"Supplies: column {need!r} not found")
    out, net, desc = [], None, ""
    for r in rows[1:]:
        if r.get(hdr["Package Net"]):
            net = r[hdr["Package Net"]]
            desc = r.get(hdr.get("Description", ""), "")
        num = r.get(hdr[PKG], "")
        if net and num:
            out.append({"pin": num, "port": net, "pad_type": "SUPPLY",
                        "pe": "", "ps": "", "description": desc})
    return out


def main():
    if not os.path.exists(XLSX):
        sys.exit(f"missing {XLSX}\nSee this file's docstring for how it is "
                 f"obtained -- it is a PDF attachment, not a download.")
    z, shared, sheets = open_book(XLSX)
    pins, alts = extract_io(z, shared, sheets)
    sup = extract_supplies(z, shared, sheets)

    allpins = [dict(p, description="") for p in pins] + sup
    seen = {}
    for p in allpins:
        seen.setdefault(p["pin"], []).append(p["port"])
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    if dupes:
        sys.exit(f"two names on one package pin, refusing to write: {dupes}")

    nums = sorted(int(p["pin"]) for p in allpins)
    missing = [n for n in range(1, 145) if n not in nums]

    os.makedirs(os.path.dirname(OUT_PINS), exist_ok=True)
    with open(OUT_PINS, "w", newline="") as f:
        w = csv.DictWriter(f, ["pin", "port", "pad_type", "pe", "ps",
                               "description"])
        w.writeheader()
        for p in sorted(allpins, key=lambda x: int(x["pin"])):
            w.writerow(p)
    with open(OUT_ALT, "w", newline="") as f:
        w = csv.DictWriter(f, ["pin", "port", "mux", "function", "module",
                               "direction"])
        w.writeheader()
        w.writerows(sorted(alts, key=lambda x: (int(x["pin"]), x["mux"])))

    print(f"{len(pins)} port pins + {len(sup)} supply pins = {len(allpins)} "
          f"of 144")
    print(f"{len(alts)} alternate functions")
    if missing:
        print(f"package pins with no row: {missing}")
    else:
        print("all 144 package pins accounted for")


if __name__ == "__main__":
    main()
