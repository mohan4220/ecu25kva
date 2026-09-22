import re, json, collections
html = open("kb.html").read()
VC = {"9": 6.3, "8": 10, "4": 16, "3": 25, "5": 50, "1": 100, "2": 200, "A": 250}
avail = collections.defaultdict(set)
for page in html.split("<page ")[1:]:
    words = [(float(a), float(b), float(c), float(d), w) for a, b, c, d, w in
             re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', page)]
    rows = collections.defaultdict(list)
    for x0, y0, x1, y1, w in words:
        rows[round((y0 + y1) / 2)].append(((x0 + x1) / 2, w))
    ys = sorted(rows)
    # header row: contains "Code" and single-char voltage codes
    hdr = None
    cases = []
    for y in ys:
        r = sorted(rows[y])
        ws = [w for _, w in r]
        if any(re.fullmatch(r"C\d{4}C2?", w) for w in ws) and not cases:
            cases = [(x, w[1:5]) for x, w in r if re.fullmatch(r"C\d{4}C2?", w)]
        if "Voltage" in ws and "Code" in ws and hdr is None:
            xc = [x for x, w in r if w == "Code"][-1]
            hdr = [(x, w) for x, w in r if x > xc and w in VC]
    if not hdr or not cases:
        continue
    # assign each header column to the case whose label is nearest on x,
    # constrained to be the closest case label to the LEFT-ish group
    def case_of(x):
        return min(cases, key=lambda c: abs(c[0] - x))[1]
    # groups: split header into runs at the case boundaries by nearest label
    colmap = [(x, VC[w]) for x, w in hdr]
    # case per column: cluster by midpoint between successive case labels
    cx = sorted(c[0] for c in cases)
    bounds = [(cx[i] + cx[i + 1]) / 2 for i in range(len(cx) - 1)]
    def case_by_bounds(x):
        k = sum(1 for b in bounds if x > b)
        return sorted(cases)[k][1]
    for y in ys:
        r = sorted(rows[y])
        ws = [w for _, w in r]
        # data row: capacitance, unit, code, J K M, then codes
        s = " ".join(ws)
        m = re.match(r"^([\d,.]+) (pF|µF) \d{3} J K M", s)
        if not m:
            continue
        c = float(m.group(1).replace(",", "")) * (1e-12 if m.group(2) == "pF" else 1e-6)
        xm = [x for x, w in r if w == "M"][0]
        for x, w in r:
            if x > xm and re.fullmatch(r"[A-Z]{2}\W?\d?¹?", w):
                col = min(colmap, key=lambda cc: abs(cc[0] - x))
                if abs(col[0] - x) < 6:
                    avail[f"{c:.3e}"].add((case_by_bounds(col[0]), col[1]))
json.dump({k: sorted(v) for k, v in avail.items()}, open("kemet_x7r.json", "w"))
for c in ["1.000e-07", "1.000e-06", "4.700e-06", "1.000e-05", "4.700e-05", "2.200e-07", "2.200e-08", "3.300e-10", "1.000e-09", "1.000e-08", "6.800e-09", "2.200e-09", "4.700e-09"]:
    print(c, sorted(avail.get(c, [])))
