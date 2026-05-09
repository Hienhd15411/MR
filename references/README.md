# Reference materials

This folder holds source-of-truth artifacts from the manual MarketWatch
workflow. Used by the AI processor and the categories tuning loop.

## What to upload here

| File | Purpose |
|---|---|
| `MR26001_MarketWatch_Database.xlsx` | The full Excel workbook with all 5 sheets |
| `Database.csv` (optional) | Just the Database sheet exported to CSV |
| `Scanning.csv` (optional) | Keywords used for Round 1 filter |
| `Coding.csv` (optional) | Topic/category/vertical taxonomy |
| `samples/*.json` (optional) | Hand-graded `processed.json` exemplars |

## Why we need this

`src/config/categories.yaml` (keywords + V-app strategic themes) and
`.claude/agents/ai-processor.md` (worked examples) are currently best-
guesses inferred from a sample weekly report. Once the actual Excel is
here, the categories + theme weights + agent examples can be tuned
1:1 against real graded articles.

## How to upload

Easiest from GitHub web UI:
1. Open this branch: `claude/market-watch-crawler-Bhj7D`
2. Navigate to `references/`
3. Click **Add file → Upload files**
4. Drag & drop the .xlsx (or .csv) and commit on the branch

Or via git:
```
cp ~/Downloads/MR26001_MarketWatch_Database.xlsx references/
git add references/MR26001_MarketWatch_Database.xlsx
git commit -m "data: upload MarketWatch Excel reference"
git push
```

Files in this folder are **not** processed by the runtime pipeline —
they're consumed by the human + AI tuning loop.
