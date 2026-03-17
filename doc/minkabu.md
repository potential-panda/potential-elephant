# Spec: Minkabu Scraper

## 1. Goal

Build the scraper for minkabu under the elephant framework

## 2. Scraping Logic

### 2.1 URL Structure

For each ticker, we need to scrape 4 pages
- https://minkabu.jp/stock/{ticker}/analysis
- https://minkabu.jp/stock/{ticker}/research
- https://minkabu.jp/stock/{ticker}/pick
- https://minkabu.jp/stock/{ticker}/analyst_consensus

**NOTE** the ticker.txt contains the tickers that ended with ".T", for minkabu, please remove the ".T"

### 2.2 Extraction Specification

For each ticker we want to visit 4 pages

- https://minkabu.jp/stock/{ticker}/analysis
- https://minkabu.jp/stock/{ticker}/research
- https://minkabu.jp/stock/{ticker}/pick
- https://minkabu.jp/stock/{ticker}/analyst_consensus

Please get the whole HTML of `#contents` as value

Every day for every ticker, we will generatew a record like below:

```
{
  id: generated unique id,
  ticker: ticker,
  analysis: the html of #contents from /analysis,
  research: the html of #contents from /research,
  pick: the html of #contents from /pick,
  analyst_consensus: the html of #contents from /analyst_consensus,
  scraped_at: datetime,
}
```


The record is saved into parquet files like:

`./data/dataset=minkabu_raw_html/ticker={ticker}/YEAR=YYYY/data.parquet`

**NOTE**
Yahoo use ticker.T, minkabu use ticker (no .T). please normlize in our system (the parquet path, content, etc) to use ticker.T.
only when we construct the url for scraping minkabu, we remove the .T in the MinkabuHarvester. the .T removal is considered as
a implementation logic for MinkabuHarvester.

