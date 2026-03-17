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

https://minkabu.jp/stock/{ticker}/analysis

- Current price
  - `#stock_header_contents > ... > div.stock_price`
  - there are multiple layers under the element, please extract the text only then concat them together
- oeverall_evaluation
  - Container: `#contents > ... > div.ly_row.md_card_ti.md_box > div.md_picksPlate > span`
   - Please get the html element text as value (買い or 売り)
- target price:
  - Container: `#contents > ... > div.ly_row.md_card_ti.md_box > div.tar > div:nth-child(1) ... > span`
   - Please get the html element text as value (please extract number. example 1,223)

https://minkabu.jp/stock/{ticker}/research

- evaluation_message
  - `#contents > ... > div.grid > ... > div.flex.flex-col.gap-4.indent-3.text-sm`
  - Please get the html element text as value (long text)


```
#all_rate > div > div > div._EvaluationGraph__graph_xyp4h_72
```

The example:

```
<div class="_EvaluationGraph__graph_xyp4h_72">
<span style="width:82.38%" class="_EvaluationGraph__item_xyp4h_80 _EvaluationGraph__item--strongest_xyp4h_83"></span>
<span style="width:3.89%" class="_EvaluationGraph__item_xyp4h_80 _EvaluationGraph__item--strong_xyp4h_83"></span>
<span style="width:9.07%" class="_EvaluationGraph__item_xyp4h_80 _EvaluationGraph__item--both_xyp4h_89"></span>
<span style="width:0.26%" class="_EvaluationGraph__item_xyp4h_80 _EvaluationGraph__item--weak_xyp4h_92"></span>
<span style="width:4.4%" class="_EvaluationGraph__item_xyp4h_80 _EvaluationGraph__item--weakest_xyp4h_95"></span>
</div>
```

The structure is kind of self-descriptive

- The percentage of the rate <span style="width:{rate}%" class="_EvaluationGraph__item_xyp4h_80 _EvaluationGraph__item--{evaluation}_xyp4h_{number}"
- Please extract the `{rate}` and `{evaluation}`
- `{evaluation}` can be  "strongest, strong, both, weak, weakest"
- `{rate}` is a float number showing how much percent of people rated the underlying `{evaluation}`


#### 2.2.2 Comments

The container of the list of comments:

```
#cmtlst > div._InfiniteBbsList__itemsBlock_1aetx_12 > ul
```

Under the list "ul", there is a list of comments, one of the comment example:

```
<li class="_InfiniteBbsList__item_1aetx_12"><article class="_BbsItem_qgr82_9"><div class="_BbsItem__headerBlock_qgr82_19"><div class="_BbsItem__userInfoBlock_qgr82_25"><a class="_BbsItem__userIcon--link_qgr82_31" href="https://finance.yahoo.co.jp/cm/personal/history/comment?user=f2a4f0504d14561b5b2b8f08415fd5c7e607809e661c99727c2ef11b707e9fcc" data-cl-params="_cl_link:uimg;_cl_position:1" data-cl_cl_index="1"><span class="_Image_184o8_1 _Image--complete_184o8_7 _Image--contain_184o8_29" style="width:32px"><span class="_Image__placeholder_184o8_10" style="padding-top:100%"></span><img src="https://s.yimg.jp/images/mb/textream/common/img/profile/default_profile_01.png" alt="f2a*****さんのアイコン" width="32" height="32" loading="lazy" class="_Image__image_184o8_17"></span></a><a class="_BbsItem__userName_qgr82_34" href="https://finance.yahoo.co.jp/cm/personal/history/comment?user=f2a4f0504d14561b5b2b8f08415fd5c7e607809e661c99727c2ef11b707e9fcc" data-cl-params="_cl_link:uname;_cl_position:1" data-cl_cl_index="2"><span>f2a*****</span></a></div><div class="_BbsItem__postDateBlock_qgr82_37"><a href="/quote/6740.T/forum/720286" class="_BbsItem__commentNo_qgr82_41" rel="nofollow" aria-label="コメント詳細画面へ遷移する" data-cl-params="_cl_link:cmtnmb;_cl_position:1" data-cl_cl_index="3">No.<!-- -->720286</a><time class="_BbsItem__postDate_qgr82_37">2026/3/16 18:43</time><button type="button" class="_BbsItem__reportButton_qgr82_52" aria-expanded="false" aria-haspopup="menu" aria-label="投稿報告メニューを開く" data-cl-params="_cl_link:report;_cl_position:1" data-cl_cl_index="4">報告</button></div></div><div class="_BbsItem__body_qgr82_84"><p>悩ましい…<br><br>売ったら後悔しそーね<br><br>でも明日は耐えの日かも<br>ここで運命が変わるかしらね<br><br>⤴️なら👍</p></div><div class="_BbsItem__actionBlock_qgr82_151"><a class="_Button_1xfks_1 _Button--small_1xfks_32 _Button--p_1xfks_107" href="https://login.yahoo.co.jp/config/login?.src=finance&amp;.done=https%3A%2F%2Ffinance.yahoo.co.jp%2Fquote%2F6740.T%2Fforum" data-cl-params="_cl_link:reply;_cl_position:1" data-cl_cl_index="5"><span class="_Button__main_1xfks_10"><span class="_MonoIcon_8bjpa_6 _MonoIcon--reply_8bjpa_180 _Button__icon_1xfks_20" aria-hidden="true"></span><span class="_Button__text_1xfks_29">返信</span></span></a><div class="_BbsItem__reactionsWrapper_qgr82_157"><p class="_BbsItem__reactionsText_qgr82_162">投資の参考になりましたか？</p><ul class="_BbsItem__reactions_qgr82_157"><li><button aria-label="はいを送る" type="button" class="_ReactionButton_vtn75_1" data-cl-params="_cl_link:good;_cl_position:1" data-cl_cl_index="6"><span class="_MonoIcon_8bjpa_6 _MonoIcon--hint_8bjpa_276 _ReactionButton__icon_vtn75_13" aria-hidden="true"></span><div class="_ReactionButton__countWrapper_vtn75_17"><span class="_ReactionButton__label_vtn75_23">はい</span><span class="_ReactionButton__count_vtn75_17">0</span></div></button></li><li><button aria-label="いいえを送る" type="button" class="_ReactionButton_vtn75_1" data-cl-params="_cl_link:bad;_cl_position:1" data-cl_cl_index="7"><span class="_MonoIcon_8bjpa_6 _MonoIcon--hintSlash_8bjpa_282 _ReactionButton__icon_vtn75_13" aria-hidden="true"></span><div class="_ReactionButton__countWrapper_vtn75_17"><span class="_ReactionButton__label_vtn75_23">いいえ</span><span class="_ReactionButton__count_vtn75_17">0</span></div></button></li></ul></div></div></article></li>
```

For the selectors in below, the starting "li" is the li (class=_InfiniteBbsList__item_1aetx_12) container of each comment.

* PostId
   - `li > article > div._BbsItem__headerBlock_qgr82_19 > div._BbsItem__postDateBlock_qgr82_37 > a._BbsItem__commentNo_qgr82_41`
   - in the href of the "a", the url is like https://.../forum/{postId}
   - please get the {postId} part from the url
   - This is the unique id for each stock. please use this id for duplicate checking for each stock.
* PostDateTime
   - `li > article > div._BbsItem__headerBlock_qgr82_19 > div._BbsItem__postDateBlock_qgr82_37 > time._BbsItem__postDate_qgr82_37`
   - please get the element text as PostDateTime. The format is like `2026/3/16 18:43`
* Author
   - `li > article > div._BbsItem__headerBlock_qgr82_19 > div._BbsItem__userInfoBlock_qgr82_25 > a._BbsItem__userName_qgr82_34`
   - in the href of the "a", the url is like https://.../comment?user={userId}
   - please get the {userId} part from the url
* Body
   - `li > article > div._BbsItem__body_qgr82_84`
   - please get the text of the element


### 2.3 Anti-Detection Measures

* **Headless Browser:** Use Playwright with `headless=True`.
* **Stealth:** Implement `playwright-stealth` to bypass basic bot detection.
* **User-Agent:** Rotate between common desktop User-Agents.
* **Randomized Jitter:** Add a random sleep of 3–8 seconds between page loads.
* **Daily Randomization:** The script should pick a random time of day for each ticker to avoid periodic detection patterns.

---

## 3. Storage Design (DuckDB + Parquet)

Since you use Parquet for trading, **DuckDB** is the ideal engine here. It allows you to write SQL against Parquet files directly.

### 3.1 Schema

```sql
CREATE TABLE yahoo_evaluations (
    id VARCHAR PRIMARY KEY,  -- Hash of ticker + post_id + author + post_datetime
    ticker VARCHAR,
    strongest NUMBER,
    strong NUMBER,
    both NUMBER,
    weak NUMBER,
    weakest NUMBER,
    scraped_at TIMESTAMP
);
```

```sql
CREATE TABLE yahoo_comments (
    id VARCHAR PRIMARY KEY,  -- Hash of ticker + post_id + author + post_datetime
    ticker VARCHAR,
    post_datetime TIMESTAMP,
    post_id VARCHAR,
    author VARCHAR,
    body TEXT,
    scraped_at TIMESTAMP
);
```


### 3.2 File Structure

Store data partitioned by date to keep queries fast

Evaulation:

`./data/dataset=yahoo_evaluations/ticker={ticker}/YEAR=YYYY/data.parquet`

Comments:

`./data/dataset=yahoo_comments/ticker={ticker}/date=YYYY-MM-DD/data.parquet`


---

## 4. Implementation Instructions for Code Agent

### Task A: The Harvester Class

Create a `YahooFinanceHarvester` class that:

1. Takes a `ticker` as input.
2. Launches a headless browser.
3. Scrapes the first 5 pages (or until 100 comments/24h limit is reached).
4. Returns a List of Dictionaries.

### Task B: The Manager Script

Create a `run_daily_scrape.py` script that:

1. Reads a `tickers.txt` file.
2. For each ticker, calculates a random delay.
3. Executes the Harvester.
4. Saves the output to the Parquet directory using DuckDB to handle the "Upsert" (Insert if not exists).

### Task C: The Query Interface

Create a helper function:
`get_comments_for_analysis(ticker, start_date, end_date)`
which returns a Pandas DataFrame for your future LLM/LightGBM processing.

