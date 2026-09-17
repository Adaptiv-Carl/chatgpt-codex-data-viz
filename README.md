# Data Viz Studio for ChatGPT and Codex

Data Viz Studio turns CSV, TSV, Excel, and JSON data into polished, self-contained interactive HTML dashboards. It profiles the data, handles report-style workbooks, generates a configurable dashboard, checks the resulting configuration, and packages Chart.js directly into the output so charts work offline.

The repository is both a plugin and a plugin marketplace. It can be installed locally by an individual Codex user or imported by a ChatGPT Enterprise workspace administrator.

## What it includes

- Automatic column-role and format detection
- Report-workbook tidying for title rows, wide periods, notes, totals, and subsets
- KPI, bar, line, area, stacked, share, distribution, cumulative, and table views
- Global filters and per-chart breakdown selectors
- Data-health reporting
- Sage, Signal, and Lilac palettes, plus custom palette generation
- Offline Chart.js bundling into one portable HTML file
- Protection against summing totals, subsets, and components together

The plugin does not include an MCP server and does not require an external account. Connected data sources require a separately installed and authorized connector.

## Live example

[Open the EMARKETER Media Outlook example dashboard](https://adaptiv-carl.github.io/chatgpt-codex-data-viz/)

The example demonstrates multi-page navigation, filters, KPI cards, scenario comparisons, interactive charts, data-health reporting, and palette switching. It contains a prepared demonstration extract rather than a live data connection.

## Repository structure

```text
.
├── .agents/plugins/marketplace.json
└── plugins/data-viz-studio/
    ├── .codex-plugin/plugin.json
    └── skills/data-viz-studio/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── assets/
        ├── references/
        └── scripts/
```

## Personal installation

Standalone skills are available in the ChatGPT desktop app's Codex environment, Codex CLI, and the Codex IDE extension. Plugins are available through the ChatGPT desktop app and Codex CLI.

### Option A: ChatGPT desktop app

1. Download this repository with **Code → Download ZIP**, then extract it to a permanent folder. Alternatively, clone it with Git.
2. Open the ChatGPT desktop app and switch to **Codex**.
3. Open **Plugins** and choose **Add Marketplace**.
4. Select the extracted repository folder. It must contain `.agents/plugins/marketplace.json`.
5. Open **Data Viz Studio** and select the plus button to install it.
6. Start a new task after installation.

### Option B: Codex CLI

Clone the repository and add it as a local marketplace:

```bash
git clone https://github.com/Adaptiv-Carl/chatgpt-codex-data-viz.git
codex plugin marketplace add "$(pwd)/chatgpt-codex-data-viz"
codex plugin add data-viz-studio@adaptiv-data-viz
```

Start a new Codex session after installation.

### Option C: install only the skill

For local Codex use without the plugin listing, copy the skill folder into the user skill directory:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R plugins/data-viz-studio/skills/data-viz-studio "$HOME/.agents/skills/"
```

Restart Codex. This local skill installation does not make the workflow available in ordinary ChatGPT web or mobile chats.

## ChatGPT Enterprise installation

A workspace administrator must import the repository marketplace before members can install the plugin.

1. In ChatGPT, open **Admin → Plugins**.
2. Select **Add → Import marketplace**.
3. For **Source**, enter only:

   ```text
   https://github.com/Adaptiv-Carl/chatgpt-codex-data-viz
   ```

4. Leave **Path** blank because `.agents/plugins/marketplace.json` is at the repository root.
5. Optionally select a branch, tag, or commit. Leaving this blank uses the default branch.
6. Select **Import marketplace** and authorize GitHub access when prompted.
7. Review the import result and open **Data Viz Studio**.
8. Set the installation policy for the required roles:
   - **Available** lets members install it themselves.
   - **Installed** installs it for those roles.
9. Members open **Plugins**, install **Data Viz Studio** if needed, and start a new chat.

Private repositories are supported, but the importing administrator's GitHub account must be able to read the repository and satisfy any GitHub organization approval requirements. Enterprise marketplace policies are configured in ChatGPT; policy values stored in the repository are not applied automatically during workspace import.

Enterprise marketplaces check GitHub for updates daily. Administrators can use **Admin → Plugins → Marketplaces → Sync now** to request an immediate update.

## Using Data Viz Studio

Upload or provide a CSV, TSV, Excel, or JSON file and ask:

```text
@data-viz-studio Turn this spreadsheet into an interactive dashboard.
```

In Codex, you can explicitly invoke the bundled skill with:

```text
$data-viz-studio Build a dashboard from this workbook.
```

The skill will normally:

1. Inspect and profile the data.
2. Tidy report-style layouts when necessary.
3. Confirm important interpretations or use reasonable defaults.
4. Build and validate a self-contained HTML dashboard.
5. Verify representative values against the source before delivery.

## Runtime requirements

The deterministic dashboard builder uses Python 3 with:

- `pandas`
- `openpyxl`
- `xlrd` only for legacy `.xls` files

Codex desktop environments may already provide a spreadsheet-capable Python runtime. If the packages are unavailable, the user or administrator must permit their installation in the relevant execution environment.

## Data handling

- Dashboard files embed the selected data in the generated HTML.
- Review sensitive and personal-data columns before sharing a dashboard.
- The plugin does not transmit data to an external service by itself.
- Connected sources are used only when the relevant connector is separately available and authorized.

## Updating

Personal installations from a local clone can be updated with:

```bash
git pull
codex plugin add data-viz-studio@adaptiv-data-viz
```

Enterprise administrators can wait for daily synchronization or choose **Sync now** in the marketplace settings.

## License

Released under [CC0 1.0 Universal](LICENSE). The bundled Chart.js library retains its own MIT license notice in the distributed source file.

## Support

Open an issue in this repository with the input format, the observed behavior, and any non-sensitive error message. Do not attach confidential datasets to public issues.
