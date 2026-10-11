# Strategy Lab — reusable research template (independent of Supply Scout)

**This is a new, standalone project.** Do not place it in the existing `supply-scout`, Gain Focus or Scalp City repositories. Make a new repository and mark it as a GitHub **Template repository** under Settings → General, after verifying its first run.

Works on iPhone via GitHub Pages. Uses free GitHub Actions and free/unofficial Yahoo Finance daily OHLCV data; no paid app credits, no broker API, no real orders.

## Fastest iPhone route: one-file bootstrap (recommended)

Download **`Strategy_Lab_iPhone_One_File_Setup.yml`** separately. Create a new public GitHub repository named `strategy-lab-template` with an initial README. On the **new repository only**, choose **Add file → Create new file**, set the full file path to `.github/workflows/strategy-lab.yml`, paste the entire standalone bootstrap YAML, then Commit. Select **Actions → Strategy Lab - Bootstrap & Backtest → Run workflow**. This one workflow unpacks the project source files, runs tests, downloads real historical charts, writes initial reports, and runs on its weekday schedule. No desktop, terminal or manually created subfolders are required. Because the starter is embedded inside the workflow, the YAML file is approximately 46 KB; ensure all lines are pasted.

After its first successful run: **Settings → Pages → Deploy from a branch → main → /(root)**. Then under **Settings → General**, enable **Template repository**. Never paste the bootstrap into Supply Scout.

If GitHub says `Resource not accessible by integration`, enable **Settings → Actions → General → Workflow permissions → Read and write permissions** for that new repository, then rerun.

The full ZIP is provided for developers who prefer importing a normal GitHub project with separate Python modules and workflows. The two installation routes are alternatives; don't upload both workflows or you'll schedule duplicate work.

## Manual full-project installation (alternative)


1. Create **a separate public repo** at <https://github.com/new> named `strategy-lab-template`, on your own GitHub account. Select **Add README** so it is initialized.
2. Extract the full project ZIP in Files. Upload the files to **the new repository only**. Keep `index.html`, `engine.py`, `runner.py`, `train.py`, `manifest.webmanifest`, `sw.js`, `icon-192.png` and `icon-512.png` at the root. Keep `strategies/`, `data/`, `results/`, `tests/` and `.github/workflows/` under their named paths. GitHub mobile's file uploader may not preserve directory structures; you can create folders by typing the full path when creating a file. If directory upload is difficult, use GitHub desktop-view or Work computer-browser mode.
3. Repository **Settings → Pages → Deploy from a branch → main → /(root) → Save**.
4. **Actions → Strategy Lab - Daily Research Backtest → Run workflow** and check the logs for the price feed and unit tests.
5. Open `https://<your-github-login>.github.io/strategy-lab-template/` in Safari and choose **Share → Add to Home Screen**.
6. Under repository **Settings → General**, tick **Template repository**. New experiments can use GitHub's **Use this template** function to create independent copies.

The first scan pulls actual **historical** adjusted OHLCV for the five example sector proxies, then creates `data/chart_cache.json` plus strategy results. GitHub Pages updates automatically when commits finish. On the iPhone dashboard, change parameters and tap **Run historical backtest** for fast client-side exploratory replay. Copy the JSON for a reproducible run and save as another `strategies/*.json` file, then use the Actions workflow's `strategy` input to run it on GitHub.

### Project map

| File | Role |
|---|---|
| `index.html` | Self-contained iPhone strategy editor, exploratory price-cache backtester, A/B comparison and outcome dashboard |
| `engine.py` | Reference Python OHLCV daily-bar rule engine with next-session entry, ATR stops and cost assumptions |
| `runner.py` | Download adjusted daily charts, run all strategy presets, save immutable-ish comparison logs and model readiness |
| `train.py` | Gated research-only logistic training from verified historical shortage episodes and 90-day matured outcomes |
| `strategies/*.json` | Editable strategy specifications; includes technical and verified-evidence presets |
| `data/verified_events.csv` | **Empty by design**; add only sources with demonstrable historical public availability dates |
| `data/chart_cache.json` | Created after first successful Github run; not bundled as fictional historical observations |
| `results/leaderboard.json` | Temporal train/holdout comparison, with a 90-day embargo |
| `.github/workflows/strategy-lab.yml` | GitHub Actions dispatch + weekday scheduled evaluation + tests |

### Limits and safeguards

- A news report's older publication date is **not proof** our system saw it then. A real historical event must be independently source-verified and supported by timestamp evidence. RSS articles collected today are not eligible by default.
- All indicator calculations use only candles **through the completed signal session**; entries are at the next session's adjusted open. If stop and target are both hit in the same candle, conservatively assume stop first. Gaps may produce losses beyond intended stops.
- Technical-only backtests can run straightaway, but the **shortage-outcome model will remain locked** until at least 80 independent verified historical episodes with enough winners and losers, dated evidence and matured 90-day stock-versus-ACWI returns.
- Training reserves a chronological holdout with a 90-day embargo; performance on that holdout is not a prediction guarantee, and repeatedly changing rules based on it risks overfitting.
- Today-selected stocks, one-price-provider limitations, liquidity, taxes, dividends, FX effects, delisted firms and bid–ask spreads create uncertainties. The scores are research statistics, not investable portfolio returns.
- No stored API keys, secrets, personal data or brokerage execution.

### Offline tests

```bash
python -m unittest discover -s tests -v
```

The `data/chart_cache.json`, `results/*.json` are generated from the host action; do not present demo/synthetic test fixtures as real trading evidence.
