#!/usr/bin/env python3
"""
Data Viz Studio — turn any tabular data into a self-contained dashboard.

  profile:  python build_dashboard.py profile DATA [--sheet NAME] [--out dashboard.json]
            Reads the data, detects column roles, writes a draft config, prints a short summary.

  build:    python build_dashboard.py build DATA --config dashboard.json --out report.html
            [--palette sage|signal|lilac] [--sheet NAME]

DATA can be .csv, .tsv, .txt, .xlsx, .xlsm, .xls or .json (list of records, or {"rows": [...]}).
"""
import argparse, json, re, sys, datetime as dt
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"

NULLS = {"", "na", "n/a", "#n/a", "null", "none", "nan", "-", "--", "unknown", "undefined", "(blank)"}
MONEY_WORDS = re.compile(r"spend|cost|revenue|sales|price|amount|budget|fee|income|profit|balance|payment|due|cash|gmv|value|margin|invoice|paid|total_?£|gbp|usd|eur", re.I)
ID_WORDS = re.compile(r"(^|[_\s-])(id|uuid|guid|key|code|ref|reference|url|link|email|phone)s?($|[_\s-])|_id$|Id$", re.I)
KEY_WORDS = re.compile(r"asset|creative|order|invoice|customer|user|account|deal|campaign|post|ad[_\s]?id|product|sku|transaction", re.I)
PREFERRED_DIMS = re.compile(r"channel|platform|brand|market|region|country|category|type|status|segment|product|campaign|source|medium|stage|tier|format|team|owner|objective|device|department", re.I)
SOURCE_VERSION_WORDS = re.compile(r"(^|[_\s-])(edition|version|vintage|release)$", re.I)
SECONDS_WORDS = re.compile(r"duration|length|seconds|secs|watch[_\s]?time|time[_\s]?on", re.I)

MAX_DIM_VALUES = 200

RATIO_RULES = [  # (label, numerator pattern, denominator pattern, scale, format)
    ("CTR", r"click", r"impression|impr", 1, "percent"),
    ("CPM", r"spend|cost", r"impression|impr", 1000, "currency"),
    ("CPC", r"spend|cost", r"click", 1, "currency"),
    ("Conversion rate", r"conversion|purchase|order", r"click|session|visit", 1, "percent"),
    ("CPA", r"spend|cost", r"conversion|purchase|lead|acquisition", 1, "currency"),
    ("ROAS", r"revenue|sales|gmv", r"spend|cost", 1, "decimal"),
    ("Engagement rate", r"engagement", r"impression|impr|reach", 1, "percent"),
    ("Margin", r"profit|margin", r"revenue|sales", 1, "percent"),
]


# ----------------------------------------------------------------- reading
def read_any(path, sheet=None):
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        xl = pd.ExcelFile(p)
        if sheet is None and len(xl.sheet_names) > 1:
            sizes = {s: xl.parse(s, header=None).shape[0] for s in xl.sheet_names}
            sheet = max(sizes, key=sizes.get)
            print(f"Sheets found: {xl.sheet_names} — using the largest: '{sheet}' (pass --sheet to choose)", file=sys.stderr)
        df = xl.parse(sheet or 0, dtype=object)
    elif ext == ".json":
        raw = json.loads(p.read_text())
        if isinstance(raw, dict):
            raw = raw.get("rows") or raw.get("data") or raw.get("records") or next((v for v in raw.values() if isinstance(v, list)), [])
        df = pd.json_normalize(raw)
        df = df.astype(object)
    else:
        sep = "\t" if ext == ".tsv" else None
        df = pd.read_csv(p, sep=sep, engine="python", dtype=str, keep_default_na=False, encoding_errors="replace")
    df.columns = [str(c).strip() or f"Column {i+1}" for i, c in enumerate(df.columns)]
    # drop fully empty columns created by spreadsheets
    df = df.loc[:, [c for c in df.columns if not str(c).startswith("Unnamed:") or df[c].notna().any()]]
    # de-duplicate column names
    seen = {}
    cols = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            cols.append(f"{c} ({seen[c]})")
        else:
            seen[c] = 0
            cols.append(c)
    df.columns = cols
    return df


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
        return v
    s = str(v).strip()
    return None if s.lower() in NULLS else s


def to_number(s):
    if s is None:
        return None, False, False
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s), False, False
    t = str(s).strip()
    money = bool(re.search(r"[£$€]", t))
    pct = t.endswith("%")
    neg = t.startswith("(") and t.endswith(")")
    t = re.sub(r"[£$€,%\s()]", "", t)
    if re.fullmatch(r"[-+]?\d*\.?\d+(e[-+]?\d+)?", t, re.I):
        x = float(t)
        if neg:
            x = -x
        if pct:
            x = x / 100
        return x, money, pct
    return None, False, False


def slug(name, used):
    k = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "col"
    if k[0].isdigit():
        k = "c_" + k
    base, n = k, 2
    while k in used:
        k = f"{base}_{n}"
        n += 1
    used.add(k)
    return k



# ----------------------------------------------------------------- tidy (report-style workbooks)
PERIOD = re.compile(r"^\s*((19|20)\d{2}(\.0+)?|FY\s?'?\d{2,4}|Q[1-4]\s?'?\d{2,4}|(19|20)\d{2}\s?Q[1-4]|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s-]?'?\d{2,4})\s*$", re.I)
TOTAL_RX = re.compile(r"(grand |sub-?)?total(\s+\S+)?|\S+\s+(sub-?)?total|all (markets|regions|channels|countries)", re.I)
SUBSET_RX = re.compile(r"^\s*(of which|incl\.?|including|o/w)\b", re.I)
DERIVED_RX = re.compile(r"\(derived\)|\bformula\b|\(check\)", re.I)


def _is_num(v):
    return to_number(clean(v))[0] is not None


def _period_label(v):
    t = str(v).strip()
    return t[:-2] if re.fullmatch(r"\d{4}\.0", t) else t


def tidy_sheet(name, grid):
    """Find header rows (text + period columns, or text headers over data), return long rows + notes."""
    g = grid.astype(object).where(pd.notna(grid), None)
    rows = g.values.tolist()
    ncol = g.shape[1]
    notes, out = [], []
    headers = []
    for i, r in enumerate(rows):
        cells = [c for c in r if clean(c) is not None]
        periods = [j for j, c in enumerate(r) if clean(c) is not None and PERIOD.match(str(c))]
        texts = [j for j, c in enumerate(r) if clean(c) is not None and not PERIOD.match(str(c)) and not _is_num(c)]
        stray_nums = [j for j, c in enumerate(r) if clean(c) is not None and j not in periods and _is_num(c)]
        if len(periods) >= 2 and texts and not stray_nums:
            headers.append((i, periods, "wide"))
        elif len(cells) >= 2 and len(texts) == len(cells) and i + 1 < len(rows) and sum(_is_num(c) for c in rows[i + 1]) >= 1 \
                and not any(h[0] < i for h in headers):
            headers.append((i, [], "flat"))
    if not headers:
        return [], [f"{name}: no table header found (skipped)"]
    header_idx = {h[0] for h in headers}
    context = None
    for hi, (h, periods, kind) in enumerate(headers):
        head = rows[h]
        end = headers[hi + 1][0] if hi + 1 < len(headers) else len(rows)
        # block title = nearest text-only single-cell row above header (not the sheet title in row 0/1)
        above = [rows[k] for k in range(max(0, h - 2), h) if sum(clean(c) is not None for c in rows[k]) == 1]
        block = str(clean(above[-1][0])) if (above and h > 3) else None
        idcols = [j for j in range(ncol) if j not in periods and clean(head[j]) is not None]
        for k in range(h + 1, end):
            r = rows[k]
            filled = [c for c in r if clean(c) is not None]
            if not filled:
                continue
            nums = sum(_is_num(r[j]) for j in (periods or range(ncol)))
            if nums == 0:
                if len(filled) == 1 and len(str(filled[0])) > 40:
                    notes.append(f"{name}: {filled[0]}")
                continue
            base = {"Sheet": name}
            if block:
                base["Block"] = block
            labels = [str(clean(r[j]) or "") for j in idcols]
            label_text = " ".join(labels)
            for j in idcols:
                base[str(head[j]).strip()] = clean(r[j])
            base["Row type"] = ("Derived" if DERIVED_RX.search(label_text) else "Subset" if any(SUBSET_RX.search(x) for x in labels)
                                else "Total" if any(TOTAL_RX.fullmatch(x.strip()) for x in labels) else "Value")
            if kind == "wide":
                for j in periods:
                    v = to_number(clean(r[j]))[0]
                    out.append({**base, "Period": _period_label(head[j]), "Value": v})
            else:
                for j in range(ncol):
                    if j not in idcols and clean(head[j]) is not None:
                        base[str(head[j]).strip()] = clean(r[j])
                out.append(base)
    # sheet title / subtitle rows above the first header
    for k in range(0, headers[0][0]):
        t = clean(rows[k][0])
        if t:
            notes.insert(0, f"{name} (title): {t}")
    return out, notes


def tidy_workbook(path, sheets=None):
    xl = pd.ExcelFile(path)
    all_rows, notes = [], []
    for sh in xl.sheet_names:
        if sheets and sh not in sheets:
            continue
        grid = xl.parse(sh, header=None, dtype=object)
        r, n = tidy_sheet(sh, grid)
        all_rows += r
        notes += n
    df = pd.DataFrame(all_rows)
    # fill "Row type": a derived flag in any cell (e.g. an Edition column saying "Formula")
    if not df.empty:
        other = [c for c in df.columns if c not in ("Sheet", "Row type", "Period", "Value")]
        mask = df[other].astype(str).apply(lambda col: col.str.contains(DERIVED_RX)).any(axis=1)
        df.loc[mask, "Row type"] = "Derived"
    return df, notes

# ----------------------------------------------------------------- profiling
def profile_df(df):
    n = len(df)
    used = set()
    cols = []
    for name in df.columns:
        raw = [clean(v) for v in df[name].tolist()]
        nonnull = [v for v in raw if v is not None]
        fill = round(100 * len(nonnull) / n) if n else 0
        info = {"name": name, "key": slug(name, used), "fill": fill, "values": raw}
        uniq = len(set(map(str, nonnull)))
        info["unique"] = uniq
        if not nonnull:
            info["role"] = "ignored"; info["why"] = "empty"
            cols.append(info); continue

        # numbers
        parsed = [to_number(v) for v in nonnull]
        okn = [p for p in parsed if p[0] is not None]
        is_num = len(okn) >= 0.9 * len(nonnull)

        # dates
        is_date = False
        if not SOURCE_VERSION_WORDS.search(name) and (not is_num or all(isinstance(v, (pd.Timestamp, dt.datetime, dt.date)) for v in nonnull[:50])):
            sample = nonnull[: min(len(nonnull), 400)]
            if any(isinstance(v, (pd.Timestamp, dt.datetime, dt.date)) for v in sample) or \
               sum(bool(re.search(r"\d{1,4}[-/.]\d{1,2}([-/.]\d{1,4})?|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", str(v), re.I)) for v in sample) >= 0.8 * len(sample):
                dayfirst = sum(bool(re.match(r"^(1[3-9]|2\d|3[01])[/.-]", str(v))) for v in sample) > 0
                parsed_d = pd.to_datetime(pd.Series([str(v) if not isinstance(v, (pd.Timestamp, dt.datetime, dt.date)) else v for v in raw], dtype=object),
                                          errors="coerce", dayfirst=dayfirst or None, format="mixed")
                ok = parsed_d.notna().sum()
                if ok >= 0.8 * len(nonnull):
                    is_date = True
                    info["dates"] = parsed_d

        lname = name.lower()
        if SOURCE_VERSION_WORDS.search(name):
            # Labels such as "Aug 2026" describe a source release, not the observation date.
            info["role"] = "dim"
        elif is_date:
            info["role"] = "date"
        elif is_num:
            vals = [p[0] for p in parsed]
            all_int = all(float(x).is_integer() for x in (p[0] for p in okn))
            info["nums"] = [to_number(v)[0] for v in raw]
            money = sum(p[1] for p in okn) >= 0.5 * len(okn) or bool(MONEY_WORDS.search(name))
            pct = sum(p[2] for p in okn) >= 0.5 * len(okn) or "%" in name or re.search(r"\brate\b|percent|pct|share", lname)
            if ID_WORDS.search(name) and all_int and uniq > 20:
                info["role"] = "ignored"; info["why"] = "looks like an ID"
            elif re.search(r"\byear\b|\bweek\b|\bquarter\b|\bmonth\b", lname) and all_int and uniq <= 60:
                info["role"] = "dim"
            elif all_int and uniq <= 7 and not money:
                info["role"] = "dim"
            else:
                info["role"] = "measure"
                if money:
                    info["format"] = "currency"
                elif pct and all(0 <= x <= 1.0000001 for x in (p[0] for p in okn)):
                    info["format"] = "percent"
                elif pct:
                    info["format"] = "pctpoints"
                elif SECONDS_WORDS.search(name):
                    info["format"] = "seconds"
                else:
                    info["format"] = "number"
        else:
            avglen = sum(len(str(v)) for v in nonnull[:500]) / min(len(nonnull), 500)
            ratio = uniq / max(len(nonnull), 1)
            if ID_WORDS.search(name) or (ratio > 0.9 and uniq > 50):
                info["role"] = "key" if (uniq < len(nonnull) and uniq > 1) else "ignored"
                info["why"] = "identifier / free text"
            elif avglen > 60:
                info["role"] = "ignored"; info["why"] = "long free text"
            else:
                info["role"] = "dim"
        # IDs that repeat can act as a "unique" counter
        if info["role"] in ("ignored", "dim") and uniq > 1 and len(nonnull) >= 1.15 * uniq and (ID_WORDS.search(name) or KEY_WORDS.search(name)) and uniq > 20:
            info["keyCandidate"] = True
        if info.get("keyCandidate") and (info["role"] == "ignored" or (info["role"] == "dim" and uniq > 40)):
            info["role"] = "key"
        if info["role"] == "key":
            info["keyCandidate"] = True
        cols.append(info)
    return cols


def date_grain(dates):
    d = dates.dropna()
    if d.empty:
        return "month"
    span = (d.max() - d.min()).days
    if span <= 45:
        return "day"
    if span <= 180:
        return "week"
    if span <= 1100:
        return "month"
    return "quarter"


def period_series(dates, grain):
    d = pd.to_datetime(dates, errors="coerce")
    if grain == "day":
        key = d.dt.normalize(); lab = key.dt.strftime("%d %b %y")
    elif grain == "week":
        key = (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize(); lab = "w/c " + key.dt.strftime("%d %b %y")
    elif grain == "quarter":
        key = d.dt.to_period("Q").dt.start_time; lab = "Q" + d.dt.quarter.astype("Int64").astype(str) + " " + d.dt.strftime("%y")
    else:
        key = d.dt.to_period("M").dt.start_time; lab = key.dt.strftime("%b %y")
    return key, lab


# ----------------------------------------------------------------- encoding
def encode(df, cols, cfg, source):
    """Build the compact DATA payload the template reads."""
    n = len(df)
    out_cols, dims, series = [], {}, []
    date_grains = cfg.get("dateGrains", {})
    for c in cols:
        role = c["role"]
        if role == "date":
            grain = date_grains.get(c["key"]) or c.get("grain") or date_grain(c["dates"])
            key, lab = period_series(c["dates"], grain)
            order = sorted({k for k in key.dropna()})
            labels_by_key = {}
            for k, l in zip(key, lab):
                if pd.notna(k):
                    labels_by_key[k] = l
            idx = {k: i for i, k in enumerate(order)}
            dims[c["key"]] = [labels_by_key[k] for k in order]
            series.append([idx[k] if pd.notna(k) else -1 for k in key])
            out_cols.append({"key": c["key"], "label": c["name"], "role": "date", "grain": grain})
        elif role == "dim":
            vals = [None if v is None else (str(int(float(v))) if isinstance(v, float) and float(v).is_integer() else str(v)) for v in c["values"]]
            counts = pd.Series([v for v in vals if v is not None]).value_counts()
            keep = list(counts.index[: MAX_DIM_VALUES - 1]) if len(counts) > MAX_DIM_VALUES else list(counts.index)
            other = len(counts) > MAX_DIM_VALUES
            # natural sort for short numeric-ish or ordinal categories, else by frequency
            if all(re.fullmatch(r"-?\d+(\.\d+)?", k) for k in keep):
                keep = sorted(keep, key=float)
            labels = keep + (["Other"] if other else [])
            idx = {k: i for i, k in enumerate(keep)}
            oi = len(keep)
            dims[c["key"]] = labels
            series.append([-1 if v is None else idx.get(v, oi) for v in vals])
            out_cols.append({"key": c["key"], "label": c["name"], "role": "dim"})
        elif role == "measure":
            series.append([None if x is None else (round(x, 6)) for x in c["nums"]])
            out_cols.append({"key": c["key"], "label": c["name"], "role": "measure", "format": cfg.get("formats", {}).get(c["key"], c.get("format", "number"))})
        elif role == "key":
            vals = c["values"]
            codes, seen = [], {}
            for v in vals:
                if v is None:
                    codes.append(None)
                else:
                    codes.append(seen.setdefault(str(v), len(seen)))
            series.append(codes)
            out_cols.append({"key": c["key"], "label": c["name"], "role": "key"})
    rows = [list(r) for r in zip(*series)] if series else []
    health = [[c["name"], c["fill"], c["unique"], c["role"]] for c in cols]
    return {"built": dt.date.today().isoformat(), "source": source, "cols": out_cols, "dims": dims, "rows": rows, "health": health}


# ----------------------------------------------------------------- draft config
def draft_config(cols, n, title):
    by = lambda r: [c for c in cols if c["role"] == r]
    dates, measures, dimcols = by("date"), by("measure"), by("dim")

    def dim_score(c):
        s = c["fill"]
        if 2 <= c["unique"] <= 12: s += 60
        elif c["unique"] <= 40: s += 30
        elif c["unique"] > MAX_DIM_VALUES: s -= 60
        if c["unique"] < 2: s -= 200
        if PREFERRED_DIMS.search(c["name"]): s += 40
        return s
    dimcols = sorted(dimcols, key=dim_score, reverse=True)
    good_dims = [c for c in dimcols if c["unique"] >= 2]
    measures = sorted(measures, key=lambda c: (c.get("format") == "currency", c["fill"], c["unique"] > 1), reverse=True)
    measures = [m for m in measures if m["unique"] > 1]
    sumable = [m for m in measures if m.get("format") in ("currency", "number")]
    key = next((c for c in cols if c.get("keyCandidate")), None)

    D = [c["key"] for c in good_dims]
    small = [c["key"] for c in good_dims if c["unique"] <= 8]
    date = dates[0]["key"] if dates else None
    cfg = {
        "title": title, "eyebrow": "Data Explorer", "palette": "signal", "currency": "£",
        "filters": D[:6], "breakdowns": D[:8],
        "rowLabel": "Rows", "pages": [],
    }
    if key:
        if key["role"] == "key":
            cfg["uniqueKey"] = {"col": key["key"], "label": "Unique " + re.sub(r"(?i)[_\s-]*(id|uuid|key|code|ref)$", "", key["name"]).strip().lower() + "s"}

    def cnt():
        return {"agg": "count"}

    # Overview
    kpis = [{"label": "Rows", "metric": cnt(), "sub": "in current selection"}]
    if cfg.get("uniqueKey"):
        kpis[0] = {"label": cfg["uniqueKey"]["label"], "metric": cnt(), "sub": "toggle to count {grain}"}
    for i, m in enumerate(sumable[:3]):
        kpis.append({"label": "Total " + m["name"], "metric": {"agg": "sum", "measure": m["key"]}, "tone": "accent" if i == 0 else ""})
    for d in good_dims[:2]:
        kpis.append({"label": d["name"], "metric": {"agg": "distinct", "dim": d["key"]}, "sub": "distinct values"})
    charts = []
    if date:
        if small:
            charts.append({"type": "stacked", "title": "Volume over time", "note": "{grain} by period", "dim": date, "series": small[0], "metric": cnt(), "breakdown": True, "breakdownField": "series", "breakdownOptions": small, "wide": True})
        else:
            charts.append({"type": "bar", "title": "Volume over time", "note": "{grain} by period", "dim": date, "metric": cnt(), "wide": True})
    for j, d in enumerate(D[:2]):
        charts.append({"type": "hbar", "title": f"{label_of(cols, d)} mix", "note": "{grain}", "dim": d, "metric": cnt(), "color": "main" if j == 0 else "second"})
    if sumable and D:
        charts.append({"type": "hbar", "title": f"{sumable[0]['name']} by {label_of(cols, D[0])}", "note": "total, all rows", "dim": D[0], "metric": {"agg": "sum", "measure": sumable[0]["key"]}, "breakdown": True})
    elif len(D) > 2:
        charts.append({"type": "doughnut", "title": f"{label_of(cols, D[2])} share", "note": "{grain}", "dim": D[2], "metric": cnt()})
    cfg["pages"].append({"id": "overview", "title": "Overview", "intro": f"Every page respects the filters above. {n:,} rows loaded.", "kpis": kpis[:8], "charts": charts})

    # Trends
    if date and measures:
        ch = []
        for i, m in enumerate(sumable[:2] or measures[:2]):
            agg = "sum" if m in sumable else "mean"
            ch.append({"type": "area", "title": f"{m['name']} over time", "note": f"{agg}, by {dates[0].get('grain', 'period')}", "dim": date, "metric": {"agg": agg, "measure": m["key"]}, "color": "main" if i == 0 else "second", "wide": i == 0})
        if D:
            ch.append({"type": "share", "title": "Mix over time", "note": "share of {grain} per period", "dim": date, "series": D[0], "metric": cnt(), "breakdown": True, "breakdownField": "series", "wide": True})
        cfg["pages"].append({"id": "trends", "title": "Trends", "intro": "How volume and key measures move over time.", "charts": ch})

    # Segments
    if len(D) >= 2:
        ser = next((k for k in small if k != D[0]), D[1])
        ch = [{"type": "share", "title": f"{label_of(cols, ser)} mix by segment", "note": "share of {grain}; switch the segment with the selector", "dim": D[0], "series": ser, "metric": cnt(), "breakdown": True, "breakdownOptions": [k for k in D if k != ser], "minGroup": 5, "showN": True, "wide": True}]
        for j, d in enumerate(D[1:4]):
            ch.append({"type": "hbar", "title": f"By {label_of(cols, d)}", "note": "{grain}", "dim": d, "metric": cnt(), "color": "second" if j % 2 else "main"})
        if measures:
            ch.append({"type": "table", "title": "Segment table", "note": "top 50, sortable by first column", "dim": D[0], "breakdown": True,
                       "metrics": [cnt()] + [{"agg": "sum" if m in sumable else "mean", "measure": m["key"]} for m in measures[:4]], "wide": True})
        cfg["pages"].append({"id": "segments", "title": "Segments", "intro": "Compare categories side by side. Use the selectors to switch the breakdown.", "charts": ch})

    # Measure deep dives
    for m in measures[:3]:
        agg = "sum" if m in sumable else "mean"
        mm = {"agg": "median", "measure": m["key"]}
        kp = [
            {"label": "Total" if agg == "sum" else "Mean", "metric": {"agg": agg, "measure": m["key"]}},
            {"label": "Median", "metric": mm, "tone": "accent"},
            {"label": "Mean", "metric": {"agg": "mean", "measure": m["key"]}},
            {"label": "P25 – P75", "metric": mm, "range": True},
            {"label": "Max", "metric": {"agg": "max", "measure": m["key"]}},
        ]
        if agg != "sum":
            kp.pop(2)
        ch = [
            {"type": "histogram", "title": f"{m['name']} distribution", "note": "frequency; final bar groups the top 2%", "measure": m["key"], "wide": True},
            {"type": "cumulative", "title": "Cumulative share", "note": "% of rows at or under each value", "measure": m["key"]},
        ]
        if D:
            ch.append({"type": "hbar", "title": f"Median {m['name']}", "note": "groups with 5+ rows", "dim": D[0], "metric": mm, "breakdown": True, "minGroup": 5, "showN": True, "color": "second"})
            if agg == "sum":
                ch.append({"type": "hbar", "title": f"Total {m['name']}", "dim": D[1] if len(D) > 1 else D[0], "metric": {"agg": "sum", "measure": m["key"]}, "breakdown": True, "wide": True})
        cfg["pages"].append({"id": "m_" + m["key"], "title": m["name"], "intro": f"Distribution and breakdowns for {m['name']}.", "kpis": kp, "charts": ch})

    # Efficiency ratios
    ratios = []
    for lab, numr, denr, scale, fmt in RATIO_RULES:
        num = next((m for m in measures if re.search(numr, m["name"], re.I)), None)
        den = next((m for m in measures if re.search(denr, m["name"], re.I) and m is not num), None)
        if num and den:
            ratios.append((lab, {"agg": "ratio", "num": num["key"], "den": den["key"], "scale": scale, "format": fmt, "label": lab}))
    if ratios and D:
        ch = []
        for i, (lab, r) in enumerate(ratios[:4]):
            ch.append({"type": "hbar", "title": f"{lab} by {label_of(cols, D[0])}", "note": "weighted: total ÷ total", "dim": D[0], "metric": r, "breakdown": True, "minGroup": 10, "color": "main" if i % 2 == 0 else "second"})
            if date and i == 0:
                ch.append({"type": "line", "title": f"{lab} over time", "dim": date, "metric": r, "wide": True})
        cfg["pages"].append({"id": "efficiency", "title": "Efficiency", "intro": "Ratios are calculated as total ÷ total within each group, not an average of row-level ratios.",
                             "kpis": [{"label": lab, "metric": r} for lab, r in ratios[:6]], "charts": ch})

    cfg["pages"].append({"id": "health", "title": "Data Health", "type": "health"})
    return cfg


def label_of(cols, key):
    return next((c["name"] for c in cols if c["key"] == key), key)


def apply_overrides(cols, cfg):
    """Let the config force column roles: {"roles": {"col_key": "dim"|"measure"|"date"|"key"|"ignored"}}"""
    roles = cfg.get("roles", {})
    for c in cols:
        r = roles.get(c["key"])
        if not r or r == c["role"]:
            continue
        if r == "measure":
            c["nums"] = [to_number(v)[0] for v in c["values"]]
            c.setdefault("format", "number")
        if r == "date":
            c["dates"] = pd.to_datetime(pd.Series(c["values"], dtype=object), errors="coerce", format="mixed")
        c["role"] = r
    return cols


# ----------------------------------------------------------------- build
def validate(cfg, data):
    keys = {c["key"]: c for c in data["cols"]}
    problems = []
    def need(k, roles, where):
        if k is None:
            return
        if k not in keys:
            problems.append(f"{where}: unknown column '{k}'")
        elif keys[k]["role"] not in roles:
            problems.append(f"{where}: '{k}' is {keys[k]['role']}, needs {'/'.join(roles)}")
    for d, vals in (cfg.get("defaultFilters") or {}).items():
        need(d, ("dim",), "defaultFilters")
    for f in cfg.get("filters", []) + cfg.get("breakdowns", []):
        need(f, ("dim", "date"), "filters/breakdowns")
    if cfg.get("uniqueKey"):
        need(cfg["uniqueKey"]["col"], ("key", "dim"), "uniqueKey")
    dims = data["dims"]
    def check_scope(o, where):
        for fld in ("where", "exclude"):
            for d, vals in (o.get(fld) or {}).items():
                need(d, ("dim", "date"), f"{where} {fld}")
                if d in dims:
                    for v in ([vals] if not isinstance(vals, list) else vals):
                        if str(v) not in dims[d]:
                            problems.append(f"{where} {fld}: '{v}' is not a value of '{d}'")
        if o.get("pick"):
            need(o["pick"].get("dim"), ("dim", "date"), f"{where} pick")
    def check_metric(m, where):
        if not m: return
        if m.get("agg") == "growth":
            need(m.get("dim"), ("dim", "date"), where); need(m.get("measure"), ("measure",), where)
            for v in (m.get("from"), m.get("to")):
                if m.get("dim") in dims and str(v) not in dims[m["dim"]]:
                    problems.append(f"{where}: growth value '{v}' not in '{m['dim']}'")
            return
        if m.get("agg") == "distinct": need(m.get("dim"), ("dim", "date"), where)
        elif m.get("agg") == "ratio": need(m.get("num"), ("measure",), where); need(m.get("den"), ("measure",), where)
        elif m.get("agg") == "share": need(m.get("dim"), ("dim",), where)
        elif m.get("agg") != "count": need(m.get("measure"), ("measure",), where)
    for p in cfg.get("pages", []):
        check_scope(p, f"page {p['id']}")
        for k in p.get("kpis", []):
            check_scope(k, f"page {p['id']} KPI '{k.get('label')}'")
            check_metric(k.get("metric"), f"page {p['id']} KPI '{k.get('label')}'")
        for c in p.get("charts", []):
            w = f"page {p['id']} chart '{c.get('title')}'"
            check_scope(c, w)
            need(c.get("dim"), ("dim", "date"), w); need(c.get("series"), ("dim", "date"), w)
            if c.get("type") in ("histogram", "cumulative"): need(c.get("measure"), ("measure",), w)
            check_metric(c.get("metric"), w)
            for m in c.get("metrics", []) or []: check_metric(m, w)
    return problems


def build(data_path, cfg, out, palette=None, sheet=None):
    df = read_any(data_path, sheet)
    cols = apply_overrides(profile_df(df), cfg)
    data = encode(df, cols, cfg, cfg.get("source") or Path(data_path).name)
    if palette:
        cfg["palette"] = palette
    problems = validate(cfg, data)
    if problems:
        print("Config problems:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        sys.exit(2)
    palettes = json.loads((ASSETS / "palettes.json").read_text())
    if cfg.get("customPalette"):
        palettes = {"custom": cfg["customPalette"], **palettes}
    tpl = (ASSETS / "template.html").read_text()
    js = (ASSETS / "chart.umd.min.js").read_text()
    safe = lambda o: json.dumps(o, separators=(",", ":"), default=str).replace("</", "<\\/")
    html = (tpl.replace("/*__CHARTJS__*/", js)
               .replace("__DATA_JSON__", safe(data))
               .replace("__CONFIG_JSON__", safe(cfg))
               .replace("__PALETTES_JSON__", safe(palettes))
               .replace("__TITLE__", (cfg.get("title") or "Data Explorer").replace("\n", " ").replace("<", "")))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html)
    print(f"Built {out} — {len(data['rows']):,} rows, {len(cfg['pages'])} pages, {Path(out).stat().st_size/1e6:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("profile"); a.add_argument("data"); a.add_argument("--sheet"); a.add_argument("--out", default="dashboard.json"); a.add_argument("--title")
    t = sub.add_parser("tidy"); t.add_argument("data"); t.add_argument("--out", default="tidy.csv"); t.add_argument("--sheets", nargs="*")
    b = sub.add_parser("build"); b.add_argument("data"); b.add_argument("--config", required=True); b.add_argument("--out", required=True); b.add_argument("--palette"); b.add_argument("--sheet")
    args = ap.parse_args()
    if args.cmd == "tidy":
        df, notes = tidy_workbook(args.data, args.sheets)
        df.to_csv(args.out, index=False)
        print(f"TIDY {len(df):,} rows -> {args.out}")
        if not df.empty:
            print("COLUMNS: " + ", ".join(df.columns))
            print("BY SHEET: " + ", ".join(f"{k} ({v})" for k, v in df["Sheet"].value_counts().sort_index().items()))
            print("ROW TYPES: " + ", ".join(f"{k} ({v})" for k, v in df["Row type"].value_counts().items()))
        for n in notes:
            print("NOTE " + n[:220])
        return
    if args.cmd == "profile":
        df = read_any(args.data, args.sheet)
        unnamed = sum(str(c).startswith("Unnamed") for c in df.columns)
        yearcols = sum(bool(PERIOD.match(str(c))) for c in df.columns)
        if unnamed >= len(df.columns) / 2 or yearcols >= 2:
            print("WARNING: looks like a report layout (title rows or periods as columns). Run `tidy` first, then shape with pandas.")
        cols = profile_df(df)
        for c in cols:
            if c["role"] == "date":
                c["grain"] = date_grain(c["dates"])
        title = args.title or Path(args.data).stem.replace("_", " ").replace("-", " ").title()
        cfg = draft_config(cols, len(df), title)
        Path(args.out).write_text(json.dumps(cfg, indent=1))
        print(f"ROWS {len(df):,} | COLUMNS {len(cols)}")
        for r in ("date", "measure", "dim", "key", "ignored"):
            items = [c for c in cols if c["role"] == r]
            if items:
                desc = ", ".join(
                    f"{c['name']} [{c['key']}]" + (f" ({c.get('format')})" if r == "measure" else f" ({c['unique']} values)" if r == "dim" else f" ({c.get('grain')})" if r == "date" else f" ({c.get('why','')})" if r == "ignored" else "")
                    for c in items)
                print(f"{r.upper()}: {desc}")
        if cfg.get("uniqueKey"):
            print(f"UNIQUE COUNTER: {cfg['uniqueKey']['label']} via [{cfg['uniqueKey']['col']}]")
        print("PAGES: " + " | ".join(p["title"] for p in cfg["pages"]))
        print(f"Draft config written to {args.out}")
    else:
        cfg = json.loads(Path(args.config).read_text())
        build(args.data, cfg, args.out, args.palette, args.sheet)


if __name__ == "__main__":
    main()
