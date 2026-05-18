# Potential Elephant

**Status:** Draft / Ideation
**Goal:** Build a medium-to-long-term investment decision-support system leveraging LLMs and AI-native data protocols (MCP).
**Target Capital:** Up to 20M JPY.
**Risk Profile:** Aggressive (targeting high returns, acceptable drawdown up to 25%).
**Target Markets:** JP Stocks/ETFs, US Stocks/ETFs, FX, Crypto.

## 1. Baseline
`potential-elephant` is a "Quantamental" advisor that leverages LLMs to automate deep financial research. It focuses on the "why" behind market moves by analyzing official disclosures and news, synthesized with technical indicators.

## 2. User Experience: A Typical Research Session
The system is designed to be your "Chief Investment Officer" (CIO) inside OpenClaw.

**Step 1: The Initial Query**
*   **User:** "Hey Elephant, check the latest earnings for Sony (6758) and give me a medium-term outlook."
*   **Agent:** 
    1.  Scans **TDnet** for the most recent earnings release and **EDINET** for the latest quarterly report.
    2.  Fetches 1 year of daily price data from **Yahoo Finance JP**.
    3.  Extracts key news headlines from **RSS feeds**.

**Step 2: The Deep Dive**
*   **Agent:** "I've analyzed the Q3 report. Revenue is up 8%, but operating margin in the gaming segment is squeezed by R&D costs. Technically, the stock is in a consolidation phase above the 200-day EMA. The 'vibe' on the BBS is cautious but long-term bullish. Should I generate a full comparison with Microsoft and Nintendo?"
*   **User:** "Yes, and include a risk assessment for my 20M JPY portfolio."

**Step 3: The Elephant Report**
*   **Agent:** Generates a structured Markdown report showing:
    *   **Recommendation:** Overweight (Accumulate on dips).
    *   **Catalysts:** New hardware cycle announcement expected in 6 months.
    *   **Risk:** Yen appreciation could hit overseas revenue.
    *   **Portfolio Impact:** "Adding 1M JPY here keeps our total drawdown risk at 18%, well within your 25% limit."

**Step 4: Periodic Monitoring**
*   **Agent (Proactive):** "User, Sony just released a Timely Disclosure about a new partnership. This reinforces our bull case. I suggest moving our stop-loss up by 3%."

## 3. AI-Native Data Architecture (MCP Priority)
The system uses the Model Context Protocol (MCP) to bridge LLMs with live financial data, ensuring the analyst agent has direct access to official sources:
- **Japanese Disclosures:**
  - **TDnet:** Timely disclosures (earnings, M&A) via `tdnet-disclosure-mcp`.
  - **EDINET:** Statutory filings (Annual/Quarterly reports) via the official EDINET API and `edinet-mcp`.
- **Market Data:**
  - **Yahoo Finance (JP/US):** For OHLCV, FX, and Crypto prices via `yfinance` and `stockprice-mcp`.
- **News:** RSS feeds (Reuters, NHK, Nikkei) and Google News for macro context.

## 3. Core Research Pillars (Powered by LLM)
- **Document Analysis:** Automated extraction of metrics and growth narratives from EDINET XBRL/PDF files and TDnet releases.
- **Narrative Synthesis:** LLMs summarize earnings calls and IR presentations to identify "catalysts" for long-term moves.
- **Technical Context:** EOD technical signals (Trend, Momentum) provide the "entry/exit" guardrails for the fundamental thesis.

## 4. Process
1. **Intelligence Gathering:** Scheduled scanning of TDnet/EDINET for watchlist symbols.
2. **Deep Analysis:** LLM-driven summary of reports, competitor comparisons, and "Fundamental Strength" scoring.
3. **Signal Integration:** Combining fundamental outlooks with Yahoo Finance technical indicators.
4. **Reporting:** Generating the "Elephant Report"—a daily/weekly high-conviction briefing.
5. **Execution:** Manual review and trade placement (e.g., via SBI).

## 5. Development Plan
- **Phase 1: Ingestion & MCP Setup**
  - Configure `tdnet-disclosure-mcp` and `edinet-mcp` for local use.
  - Build Python connectors for Yahoo Finance (US/JP) using `yfinance`.
  - Implement PDF/XBRL extraction for Japanese reports.
- **Phase 2: LLM Analyst Implementation**
  - Develop specialized prompts for analyzing financial statements and news.
  - Integrate with local LLMs (Ollama) or cloud APIs (Claude/Gemini).
- **Phase 3: Scoring & Reporting Engine**
  - Create the algorithm for the "Fundamental + Technical" composite score.
  - Build the automated "Elephant Report" template.
- **Phase 4: Experimental Sentiment**
  - Add Yahoo Finance Japan BBS and social media sentiment as secondary signals.
