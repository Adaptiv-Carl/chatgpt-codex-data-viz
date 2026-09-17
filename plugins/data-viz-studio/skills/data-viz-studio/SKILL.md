---
name: data-viz-studio
description: Create a polished, self-contained interactive HTML dashboard from uploaded or accessible CSV, TSV, Excel, or JSON data. Use when the user asks to visualize, explore, chart, or build a dashboard from tabular data. Also use for connected data only when the required connector or plugin is available and authorized.
---

# Data Viz Studio

Build a dashboard in the included house style without hand-writing chart code. Get the data into a local file, profile it, refine the generated JSON config, build the HTML, verify key values, and return the finished file.

The user's instructions take precedence over this workflow.

## Included resources

- `scripts/build_dashboard.py`: `tidy`, `profile`, and `build` commands.
- `scripts/make_palette.py`: generates a custom palette object.
- `assets/template.html`: dashboard engine. Prefer config changes over per-dashboard template edits.
- `assets/palettes.json`: Sage, Signal, and Lilac palettes.
- `assets/chart.umd.min.js`: bundled Chart.js for offline charts.
- `references/config-reference.md`: config schema and chart options. Read before changes beyond small config edits.
- `references/design-system.md`: palette and design rules. Read when creating or changing a palette.

The scripts require Python 3 with a current `pandas` release and `openpyxl`; legacy `.xls` input may also require `xlrd`. Check whether they are available before running the workflow. If not, ask for permission before installing packages or use an already available spreadsheet runtime. Do not use system-wide installation flags by default.

Set paths from the current workspace rather than assuming a product-specific home directory. Put intermediate files in a workspace scratch or `work/` directory and final user-facing files in the environment's designated output directory.

## Workflow

### 1. Acquire and normalize the data

- For an uploaded CSV, TSV, Excel, or JSON file, use its local path.
- For a connected source, use only tools that are actually available and authorized. Fetch all required pages, flatten nested records to one object per row, and save a local JSON or CSV snapshot. Report the row count and date range. If the connector is unavailable, ask the user to upload an export or install/connect the relevant plugin; do not invent a tool name.
- Keep source files unchanged. Never place credentials, secrets, bank details, or personal-data columns in a dashboard unless the user explicitly requests those fields.

For multi-sheet Excel files, `profile` selects the largest sheet and reports the choice. Pass `--sheet` when another sheet is intended.

For report-style workbooks with title rows, periods as columns, subtotals, or notes, run:

```bash
python3 scripts/build_dashboard.py tidy WORKBOOK.xlsx --out work/tidy.csv [--sheets "Sheet A" "Sheet B"]
```

Read every emitted `NOTE`. Then reshape the tidy output so:

- each measure column has one unit;
- series names are readable and unique;
- a `Level` column distinguishes components, subsets, groups, and totals;
- totals and subset rows cannot be accidentally stacked with their parts.

Values stated only in notes may be added only when they are figures from the source. For report-style workbooks, build intentional pages with pinned charts (`where`, `pick`, `growth`) instead of relying on the automatic draft.

### 2. Profile

From the skill directory, run:

```bash
python3 scripts/build_dashboard.py profile DATA --title "Readable Title" --out work/dashboard.json
```

Review detected dates, measures, dimensions, unique counters, ignored columns, formats, and drafted pages. Treat detection as a draft, not ground truth. Columns whose names end in `edition`, `version`, `vintage`, or `release` should be categorical dimensions even when their values resemble dates such as `Aug 2026`. Confirm this in the profile and, for an unusual name the profiler cannot recognize, set an explicit override such as `"roles": {"forecast_edition": "dim"}`.

### 3. Confirm the interpretation when needed

Summarize the row count and date range, main measures, proposed filters, proposed pages, and any questionable detections. Ask at most one focused question at a time when the answer would materially change the dashboard. If the user says to build it without review, proceed with reasonable defaults.

Offer Signal as the default palette, with Sage for a softer look and Lilac for a pastel look. Every dashboard includes a palette switcher unless `lockPalette` is enabled.

### 4. Refine the config

Read `references/config-reference.md` before substantial edits. Typical changes include:

- write a concise page `intro` grounded in computed facts;
- give charts descriptive titles;
- remove weak measures such as IDs or near-constant columns;
- set `currency`, `eyebrow`, `palette`, `roles`, `formats`, and `dateGrains`;
- add pages that answer the user's actual questions;
- create `customPalette` with `scripts/make_palette.py` after reading `references/design-system.md`.

Compute every stated number from the data. Never invent figures.

### 5. Build, verify, and deliver

```bash
python3 scripts/build_dashboard.py build DATA --config work/dashboard.json --out OUTPUT/dashboard.html
```

Fix all validation errors and rebuild. Check several KPI and grouped values against the source with an independent calculation. Open or preview the HTML when the environment supports it and confirm the page renders without dashboard errors.

Return the HTML as a downloadable local artifact. Mention what it contains, one verified observation if useful, and that the palette switcher is at the bottom left. Publish or host it only if the user explicitly asks.

## Data rules

- Counts follow the unique-versus-rows grain toggle. Sums, means, and ratios use all filtered rows. Explain this in a page intro where it matters.
- Calculate ratios such as CTR, CPM, and ROAS as total numerator divided by total denominator per group, never as the mean of row-level ratios.
- Never sum across incompatible `Level` values or add subset rows to their parents.
- For files above roughly 150,000 rows, aggregate to the required grain before building; aim to keep the embedded HTML below 25 MB.
- Preserve the source file, the generated config, and the final dashboard separately so the result is reproducible.
