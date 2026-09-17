# Config reference (`dashboard.json`)

Column keys are the slugs shown in square brackets by `profile` (e.g. `Spend (£)` → `spend`).

## Top level
| Field | Meaning |
|---|---|
| `title` | Sidebar title. Use `\n` for line breaks. |
| `eyebrow` | Small uppercase label above the title (accent colour). |
| `palette` | `sage` \| `signal` \| `lilac` \| `custom`. |
| `customPalette` | Palette object, same keys as `assets/palettes.json` (see design-system.md). |
| `lockPalette` | `true` hides the palette switcher. |
| `currency` | Symbol for currency formats. Default `£`. |
| `filters` | Dimension keys shown as filter pills (max ~7). |
| `breakdowns` | Dimension keys offered in "Break down by" selectors. |
| `uniqueKey` | `{"col": "creative_id", "label": "Unique creatives"}` — adds the grain toggle. |
| `rowLabel` | Name for rows in the toggle, e.g. `"Placements"`. |
| `roles` | Force roles: `{"key": "dim"\|"measure"\|"date"\|"key"\|"ignored"}`. |
| `formats` | Force measure formats: `number` \| `currency` \| `percent` (stored 0–1) \| `pctpoints` (stored 0–100) \| `seconds` \| `decimal`. |
| `suffix` | Unit after values: `{"ad_spend_bn": "bn"}` → `$57.1bn`. |
| `ordered` | Dims to keep in natural order (numeric labels like years are ordered automatically). |
| `defaultFilters` | Filters applied on load and on reset: `{"level": ["Component"]}`. |
| `dateGrains` | `{"date_key": "day"\|"week"\|"month"\|"quarter"}`. |
| `fonts` | `{"heading": "Sora, sans-serif", "body": "'DM Sans', sans-serif"}` (must be loadable or system fonts). |
| `pages` | List of pages (below). |

## Page
```json
{"id": "overview", "title": "Overview", "intro": "Text. {grain} and {rows} are replaced live.",
 "kpis": [...], "charts": [...]}
```
`{"id": "health", "title": "Data Health", "type": "health"}` renders the column fill-rate table.

## Metric
| `agg` | Needs | Notes |
|---|---|---|
| `count` | — | Follows grain toggle. |
| `distinct` | `dim` | Number of distinct values. |
| `sum`, `mean`, `median`, `min`, `max`, `p25`, `p75` | `measure` | Ignores blanks. |
| `ratio` | `num`, `den`, optional `scale` | Σnum ÷ Σden × scale. Set `format` (e.g. CTR `percent`, CPM `currency` with scale 1000). |
| `share` | `dim`, `value` | Share of rows where dim = value (percent). |
| `growth` | `measure`, `dim`, `from`, `to`; optional `of` (default `sum`), `cagr: true`, `periods` | Change from one value of an ordered dim to another. With `cagr`, annualised over the numeric gap (2024→2028 = 4 years). Works per group in `hbar`. |

Optional on any metric: `label`, `format`.

## Pinning rows: `where`, `exclude`, `pick`
Any page, KPI or chart can carry:
- `"where": {"dataset": ["Retail media"], "market": ["UK"], "year": ["2026"]}` — keep only these values.
- `"exclude": {"market": ["Worldwide"]}` — drop these values.
- `"pick": {"dim": "year", "default": "2026", "label": "Year"}` (charts only) — adds a dropdown that pins one value.

A dim pinned by `where`/`pick` ignores the global filter for that dim, so a "Worldwide 2026" tile stays correct when the user filters to UK. Page-level `where` applies to everything on the page. Values must match the data exactly; the build reports typos.

## KPI tile
`{"label": "Median spend", "metric": {...}, "sub": "small grey line", "tone": "accent"|"good"|"bad"}`
Add `"range": true` with a measure metric to show P25–P75. `"signed": true` shows a + on positive values (growth). KPIs accept `where`/`exclude`.

## Charts
Shared options: `title`, `note`, `where`, `exclude`, `pick`, `wide` (full width), `tall` (420px), `color` (`main`|`second`|`accent`|`good`|`bad`|hex), `topN`, `minGroup` (hide groups with fewer rows), `showN` (append row counts to labels; off by default). Series named Other/Unknown are drawn last in grey.

| `type` | Required | Use for |
|---|---|---|
| `bar` | `dim`, `metric` | Vertical bars; dates stay in time order. |
| `hbar` | `dim`, `metric` | Ranked categories. `ascending: true` to flip. `colorBy: "sign"` for +/- values. |
| `doughnut` | `dim`, `metric` | Parts of a whole, ≤8 values. Use sparingly. |
| `line` / `area` | `dim` (usually a date), `metric` or `metrics: [...]` | Trends. Add `series` to split into lines (top 5). |
| `stacked` | `dim`, `series`, `metric` | Absolute stacked bars. `horizontal: true` optional. |
| `share` | `dim`, `series`, `metric` | 100% stacked mix. `semantic: true` colours 3 series good/grey/bad (e.g. tiers). |
| `histogram` | `measure` | Distribution. `bins`, `min`, `max` optional (default caps at P98 with a "+" bar). |
| `cumulative` | `measure` | Cumulative % at or under each value. |
| `table` | `dim`, `metrics: [...]` | Group table, sorted by first metric. |

`palette` on `stacked`/`share`: `seqMain` (default) or `seqSecond`.

### Breakdown selectors
`"breakdown": true` adds a "Break down by" dropdown to the card. By default it swaps `dim`; set `"breakdownField": "series"` to swap the series instead (e.g. time charts). Limit choices with `"breakdownOptions": [...]`.

## Example chart set (placements export)
```json
{"type":"share","title":"Asset type by channel","dim":"channel","series":"asset_type","metric":{"agg":"count"},"breakdown":true,"minGroup":15},
{"type":"hbar","title":"CPM by channel","dim":"channel","metric":{"agg":"ratio","num":"spend","den":"impressions","scale":1000,"format":"currency","label":"CPM"},"minGroup":20},
{"type":"histogram","title":"Video length","measure":"video_length_s","bins":30,"max":60,"wide":true}
```
