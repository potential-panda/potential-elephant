# Yahoo Japan Finance BBS Scraper (Phase 1)

Headless scraping pipeline for Yahoo Japan Finance BBS comments and evaluations.

## Setup

1. Install dependencies:
   ```bash
   pip install playwright playwright-stealth duckdb pandas pyarrow
   playwright install chromium
   ```

2. Create `tickers.txt`:
   Add one ticker per line (e.g., `7203` or `6758`).

## Usage

### Run Daily Scrape

```bash
# Dry run to see the plan
python src/cli.py schedule --dry-run

# Run the long-running scheduler
python src/cli.py schedule
```

### Fetch for Testing

```bash
python src/cli.py fetch --dataset=yahoo_comments
```

- Scrapes random 5 stocks.
- Displays the most recent data on the console.

### Query Stored Data

```bash
# Get most recent 200 comments
python src/cli.py query --dataset yahoo_comments --ticker 7203

# Get comments for a specific date
python src/cli.py query --dataset yahoo_comments --ticker 7203 --start 2026-03-16

# Get comments for a date range
python src/cli.py query --dataset yahoo_comments --ticker 7203 --start 2026-03-01 --end 2026-03-16
```

### Query Data for Analysis

Use the `query_interface.py` to get data into Pandas:

```python
from query_interface import get_comments_for_analysis

df = get_comments_for_analysis('7203.T', '2026-03-16', '2026-03-16')
print(df.head())
```

## Data Structure

- **Evaluations:** `./data/dataset=yahoo_evaluations/ticker={ticker}/YEAR={year}/data.parquet`
- **Comments:** `./data/dataset=yahoo_comments/ticker={ticker}/date={date}/data.parquet`

## Anti-Detection Measures

- **Headless Browser:** Playwright.
- **Stealth:** `playwright-stealth`.
- **User-Agent:** Randomized rotation.
- **Jitter:** Random sleep (3-8s) between page loads.
- **Randomization:** Random delay (10-60s) between tickers.
