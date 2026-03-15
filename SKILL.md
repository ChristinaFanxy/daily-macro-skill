---
name: daily-macro-en
description: |
  Daily Macro Strategy Analyst for financial markets. Generates professional macro strategy reports
  analyzing core market narratives, cross-asset logic, and actionable watchlists.

  TRIGGER when: user says "每日宏观", "daily macro", "今日市场", "宏观分析", "macro briefing",
  "市场速览", "market overview", "宏观速报", "macro", "econ", "宏观", "经济", or uses /daily-macro command.

  Supports --brief (quick 3-point summary, default) and --full (comprehensive analysis with
  pain trade, historical playbooks) modes.
---

# Daily Macro Strategy Analyst

## Core Philosophy

**This is not a data aggregator, but a macro strategy analyst.**

The analyst's value lies in:
1. **Identifying today's core narrative** — The "master switch" driving all asset pricing
2. **Building causal chains** — What happened → Why it matters → Impact on markets
3. **Providing actionable watchpoints** — Specific price levels, time points, trigger conditions
4. **Flagging risks** — Under what circumstances the logic would be invalidated

---

## Parameters

- `--brief` : Quick summary (core narrative + 3 watchpoints + 1 risk) **[Default]**
- `--full` : Full report (data dashboard + trade implications + Pain Trade + historical playbook)

---

## Execution Flow Overview

```
PHASE 1: Data Fetch & Calculation → PHASE 2: Core Narrative ID → PHASE 3: Cross-Asset Validation
    ↓                                                              ↓
PHASE 4: Watchlist ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
    ↓
PHASE 5: Risk Alerts → PHASE 6: Output Generation
```

---

## Environment Variable Configuration

Before using this skill, ensure the `.env` file contains the following API keys:
```bash
FRED_API_KEY=your_key
FINNHUB_API_KEY=your_key
TWELVE_DATA_API_KEY=your_key
NEWSAPI_KEY=your_key
ALPHA_VANTAGE_KEY_1=your_key
ALPHA_VANTAGE_KEY_2=your_key
```

---

# PHASE 1: Data Fetch & Calculation

**Run the script once to complete both data fetching and metric calculation. All mathematical calculations must be done by the script; the LLM is prohibited from calculating values independently.**

## Execution Steps

**Step 1: Run the script to fetch data**
```bash
python3 scripts/calc_metrics.py --markdown
```
The script will automatically save data to `data/YYYY-MM-DD.json` and generate a pre-filled dashboard template at `data/YYYY-MM-DD-dashboard.md`. Old data files (>3 days) are automatically cleaned up.

**Step 2: Read the data file**
```bash
# Read today's data file
cat data/$(date +%Y-%m-%d).json
```
**⚠️ Mandatory Rule**: Data must be read from the JSON file in the `data/` directory. Parsing from script stdout output is prohibited to avoid data loss.

**Other Options:**
```bash
# Pass custom data (skip data fetch, calculate only, don't save)
python3 scripts/calc_metrics.py -i '{"dgs10": 4.15, "dgs2": 3.57, ...}' --no-save

# Don't save to file
python3 scripts/calc_metrics.py --no-save
```

**Detailed API Configuration**: See [references/phase1-data-sources.md](references/phase1-data-sources.md)

## Script Output Structure

The script outputs JSON containing two parts:

**`fetched` — Raw Data**:
- FRED data (rates, VIX, FX, equity indices)
- Commodity prices (WTI, Gold, Copper via Stooq/TwelveData)

**`calculated` — Calculated Results**:
- `spread_2s10s` — 2s10s spread (bp) and inversion status
- `curve_shape` — Curve shape (Bear/Bull Steepener/Flattener)
- `breakeven` — Breakeven inflation expectation and calculation formula
- `*_change` — Price changes for each asset
- `divergences` — Auto-detected divergence patterns (8 types)

**⚠️ Mandatory Rule**: All values cited in the report must come from script output. LLM self-calculation is prohibited.

## Data Source Priority

| Data Type | Primary Source | Fallback |
|-----------|----------------|----------|
| Treasury Yields/VIX | FRED | WebSearch |
| Crude Oil/Gold/Copper | Stooq / TwelveData | FRED (lagged) |
| FX (DXY, USD/JPY) | FRED | Twelve Data |

## Parallel Fetch Batches

```
Batch A (FRED): DGS2, DGS10, DGS30, T10Y2Y, DFII10, T10YIE, VIXCLS, BAMLH0A0HYM2, DTWEXBGS, DEXJPUS, SP500
Batch B (Stooq/TwelveData): WTI (cl.f), Gold (XAU/USD), Copper (hg.f)
```

**Note**: News fetching occurs during Phase 2 Core Narrative Identification, not in this phase.

## Key Calculations (Automatically Done by Script)

| Metric | Formula | Purpose | Output Label |
|--------|---------|---------|--------------|
| 2s10s Spread | Prefer T10Y2Y, fallback DGS10 - DGS2 | Curve shape | Auto-validated by script |
| Real Rate | DFII10 direct read | Gold pricing | Raw data |
| **Breakeven Inflation** | Prefer T10YIE, cross-check DGS10 - DFII10 | Inflation expectations | `[Derived: 10Y - TIPS]` |
| Copper/Gold Ratio | Copper price / Gold price | Economic expectations | `[Derived: Cu/Au]` |
| Curve Shape | Compare 10Y/2Y movement direction and magnitude | Macro judgment | Bear/Bull Steepener/Flattener |

**Unit Standards:**
- Copper: $/lb (COMEX HG contract)
- Crude Oil: $/bbl
- Gold: $/oz
- Spread: bp (basis points)

---

# PHASE 2: Core Narrative Identification

**Detailed Specification**: See [references/phase2-core-narrative.md](references/phase2-core-narrative.md)

## Priority Decision Tree (Stop on First Match)

| Priority | Type | Trigger Condition |
|----------|------|-------------------|
| 1 | Geopolitical Conflict/Black Swan | Keyword match + Asset anomaly (Gold >2%, Oil >5%, VIX >25) |
| 2 | Central Bank Surprise | Fed/ECB/BOJ unexpected hike/cut, dot plot major shift |
| 3 | Major Data Beat/Miss | CPI deviation >0.3%, NFP deviation >100K |
| 4 | Commodity Violent Move | Oil >5%, Gold >3%, Copper >4% |
| 5 | Key Technical Breakout | 10Y breaks round number, DXY breaks 105/110 |
| 6 | Routine Market | None of above triggered → "Awaiting catalyst" |

## Lifecycle Labels (Mandatory for Geopolitical/Central Bank Events)

| Phase | Judgment Criteria | Trade Implication |
|-------|-------------------|-------------------|
| `[T+0 Outbreak]` | New outbreak <24h | Go long safe havens |
| `[T+N Stalemate]` | Occurred but not escalating | **Mandatory label `[⚠️ Priced-in]`**, don't chase |
| `[De-escalation]` | Peace talks/ceasefire signals | Flag fade opportunity |

## Data Impact Matrix

| Data | Above Expectations | Below Expectations |
|------|--------------------|--------------------|
| CPI/PCE | Treasuries↓ USD↑ Gold↓ Equities↓ | Treasuries↑ USD↓ Gold↑ Equities↑ |
| NFP | Treasuries↓ USD↑ Equities↑(soft landing) | Treasuries↑ USD↓ Equities↓(recession fear) |
| Unemployment | Treasuries↑ USD↓ Equities↓ | Treasuries↓ USD↑ Equities↑ |

---

# PHASE 3: Cross-Asset Logic Validation

**Detailed Specification**: See [references/phase3-macro-regimes.md](references/phase3-macro-regimes.md)

## Core Asset Correlations

| Asset Pair | Normal Correlation | Logic Basis |
|------------|-------------------|-------------|
| Real Rate (DFII10) vs Gold | Negative | Real rate↑ → Gold opportunity cost↑ |
| USD (DXY) vs Gold | Negative | USD-denominated, strong USD = weak Gold |
| Oil vs Treasury Yields | Positive | Oil↑ → Inflation expectations↑ → Yields↑ |
| VIX vs Equities (SPX) | Negative | Fear↑ → Equities↓ |
| Copper/Gold Ratio vs Economic Outlook | Positive | Copper is economic bellwether |

## Four Macro Regimes

| Regime | Growth | Inflation | Key Characteristics |
|--------|--------|-----------|---------------------|
| 🟢 Goldilocks | ↑ | ↓ | Equity euphoria, Gold under pressure |
| 🟡 Reflation | ↑ | ↑ | Copper/Oil surge, Cyclicals beat Growth |
| 🔴 Stagflation | ↓ | ↑ | **Stocks & Bonds both down (SPX↓ + 10Y Yield↑)**, Cash is king |
| ⚫ Recession | ↓ | ↓ | Treasuries surge, Equities crash |

### 🔴 Stagflation Identification (Most Dangerous)

**Core Characteristics (by weight):**
1. **Highest Weight**: Stocks & Bonds both down (SPX↓ + 10Y Yield↑) — This is the essential feature of stagflation
2. **High Weight**: Commodities rising (Oil↑, Copper↑)
3. **Secondary Reference**: USD direction — Can be strong or weak, depends on US vs other economies' relative performance

**⚠️ Stagflation Special Rules:**
- Must warn: "In current stagflation environment, stocks and bonds may both decline, traditional 60/40 portfolio fails"
- Must calculate Copper/Gold ratio, declining ratio = weakening economic expectations

## Eight Divergence Patterns

### Pattern 1: Real Rate Divergence — TIPS Yield (DFII10)↑ + Gold↑
- **Normal Logic**: Real rate↑ → Gold opportunity cost↑ → Gold↓
- **Divergence Criteria**: DFII10 rises >5bp AND Gold rises >1% simultaneously
- **⚠️ Note**: If nominal yield (DGS10)↑ but Breakeven (inflation expectations)↑ more, then real rate↓, Gold↑ is normal, not divergence
- **Must Calculate**: Breakeven = DGS10 - DFII10, determine inflation expectation change
- **Danger Level**: ⚠️ Trend reversal signal

### Pattern 2: Options Anomaly — SPX Surges↑ + VIX Spikes↑
- **Divergence Criteria**: SPX >0.5% AND VIX same direction >5%
- **Danger Level**: 🔴 **Topping signal**

### Pattern 3: Stagflation Pricing — Stocks & Bonds Both Down + Commodities↑
- **Core Feature**: SPX↓ + 10Y Yield↑ + Oil/Copper↑ occurring simultaneously
- **⚠️ Note**: USD direction uncertain, depends on relative economic performance
- **Danger Level**: 🔴 **Extremely dangerous**

### Pattern 4: Recession Confirmation — Treasury Yields Plunge↓ + Gold Surges↑
- **Criteria**: 10Y >10bp AND Gold >1.5% violent moves simultaneously
- **Danger Level**: ⚠️ Recession trade confirmed

### Pattern 5: Liquidity Crisis — Gold↓ + Equities↓ + Treasury Yields↑ ☠️
- **Prerequisite**: Must be accompanied by HY OAS significant widening (>50bp single day), otherwise just technical adjustment
- **Danger Level**: ☠️ **Maximum danger** (March 2020, Lehman 2008)
- **Trade Implication**: Only cash and short-term Treasuries are safe, wait for Fed rescue

### Pattern 6: Carry Unwind — USD/JPY Plunges↓ + US Equities Crash↓ + VIX Spikes↑ 🔴
- **Criteria**: USD/JPY single day >1.5% **AND** VIX >20% simultaneously
- **⚠️ Exclusion**: If USD/JPY slowly declining + VIX stable → Normal rate differential narrowing, not divergence
- **Pre-check**: Is US-Japan 10Y spread narrowing? If yes, JPY appreciation may be normal rate-driven
- **Danger Level**: 🔴 **Cascade liquidation warning**
- **Historical Case**: August 2024 "Black Monday"

### Pattern 7: Copper/Gold Ratio Divergence — Copper/Gold Ratio↓ + 10Y Treasury Yield↑
- **Danger Level**: 🔍 **Opportunity signal**
- **Verification Method**: Watch PMI, industrial output and other real economy data

### Pattern 8: Fiat Credit Hedge — DXY↑ + Gold↑ Both Rising ☠️
- **Divergence Criteria**: DXY >0.5% AND Gold >1% rising together
- **Macro Explanation**: Capital simultaneously buying USD (ultimate liquidity) and Gold (ultimate safe haven), market hedging "all fiat currency" risk
- **Danger Level**: ☠️ **Extreme tail risk**
- **Trade Implication**: Extreme risk-off mode, beware systemic risk, consider increasing physical assets

## Divergence Detection Thresholds

| Divergence Type | Significance Threshold |
|-----------------|------------------------|
| Equities vs VIX | SPX >0.5% AND VIX same direction >5% |
| Real Rate vs Gold | DFII10 >5bp AND Gold same direction >1% |
| USD vs Commodities | DXY >0.5% AND Oil/Copper same direction >1.5% |
| JPY vs Risk Assets | USD/JPY >1.5% AND VIX >20% |
| DXY vs Gold Both Rising | DXY >0.5% AND Gold >1% rising together |

## VIX Divergence Detection (Mandatory Even in Brief Mode)

If geopolitical conflict/major risk event persists but VIX significantly retreats (>10%), must label:
> "⚠️ VIX diverges from risk event: VIX fell from [X] to [Y], market panic marginally subsiding, don't chase safe havens"

---

# PHASE 4: Watchlist Generation

**Detailed Specification**: See [references/phase4-5-watchlist-risk.md](references/phase4-5-watchlist-risk.md)

## Quantity Requirements

| Mode | Quantity |
|------|----------|
| `--brief` | 3 items |
| `--full` | 4-5 items |

## Each Item Must Include

1. **Asset** + specific price level
2. **Trigger condition** → Expected reaction
3. **Invalidation condition** → Opposite expectation
4. **💥 Pain Trade** (Full mode mandatory): Which direction is crowded

## Pain Trade Data Sources

**CFTC COT Positioning (Free Official API):**
```bash
# Disaggregated Futures
curl -s "https://publicreporting.cftc.gov/resource/72hh-t7tf.json?\$limit=10&\$order=report_date_as_yyyy_mm_dd DESC"
```
- Key fields: `pct_of_oi_m_money_long/short` (Managed money long/short percentage)
- Updates: Released every Friday, data lagged ~3 days, label `[CFTC COT T-3]`

**Options Gamma:**
- Pre-calculated GEX has no free API, must calculate from options chain or WebSearch
- Tradier Sandbox can get options chain Greeks

**WebSearch Fallback Keywords:**
```
"SPY gamma exposure" site:spotgamma.com
"[ticker] dealer positioning"
"CFTC COT [asset] positioning"
```

**Output Labels:**
- COT data → `[CFTC COT T-3]`
- WebSearch inference → `[Based on news inference]`
- Unable to obtain → `[Positioning data unavailable]`

## Mandatory Constraints

1. **At least 1 item linked to core narrative**
2. **At least 1 regime verification point** (Full mode)
3. **No vague statements**: ❌"Watch oil prices" → ✅"WTI $85 support, break below targets $80"

## Regime Verification Point Examples

| Current Regime | Verification/Invalidation Point |
|----------------|--------------------------------|
| Goldilocks | VIX breaks [X] or credit spreads widen [Y]bp → Regime shift |
| Reflation | Copper breaks below $[X] → Reflation thesis invalidated |
| Stagflation | Oil breaks below $[X] AND USD weakens → Stagflation pressure easing |
| Recession | Copper rebounds [X]% → Recession expectations may be overdone |

---

# PHASE 5: Risk Alert Generation

**Detailed Specification**: See [references/phase4-5-watchlist-risk.md](references/phase4-5-watchlist-risk.md)

## Quantity Requirements

| Mode | Quantity |
|------|----------|
| `--brief` | 1 item |
| `--full` | 1-2 items |

## Must Include

1. **Risk name** + trigger condition
2. **Pricing status** (Unpriced/Partially priced/Fully priced)
3. **Affected assets** + response recommendation
4. **Second-order transmission** (Full mode mandatory)

## Pricing Status Assessment

| Pricing Status | Judgment Criteria | Risk Threat |
|----------------|-------------------|-------------|
| Unpriced | Market consensus opposite, hedge cost extremely low | ☠️ Extreme |
| Partially Priced | Some preparation, positions not fully adjusted | 🔴 High |
| Fully Priced | Rate futures/options already reflect | ⚠️ Limited, may "Sell the fact" |

## Mandatory Constraints

1. **Must oppose core narrative**: Risk is the "opposite" of core narrative
2. **Unpriced AND cheap hedge** → Label "🎯 Asymmetric opportunity"
3. **During stagflation/liquidity crisis** → Warn "Traditional hedges may fail"

---

# PHASE 6: Output Generation

**Detailed Templates**: See [references/phase6-templates.md](references/phase6-templates.md)

## Brief Mode Structure

```markdown
# 📊 Daily Macro Strategy | [Regime Label]
**Date**: YYYY-MM-DD

## 🎯 Today's Core Narrative [Lifecycle Label]
**[One-line thesis]**
[2-3 sentence causal chain analysis]

## 📋 Today's Watchlist (3 items)
1️⃣ **[Asset] [Level]**: [Trigger] → [Expected]; [Invalidation] → [Opposite]
2️⃣ ...
3️⃣ ...

## ⚠️ Risk Alert
**[Risk Name]** [Level]: [Trigger] → [Impact] | Pricing: [Status] | Response: [Recommendation]

---
*Generated: YYYY-MM-DD HH:MM UTC*
*Disclaimer: For reference only, not investment advice*
```

## Full Mode Structure

```markdown
# 📊 Daily Macro Strategy Report | [Regime Label]
**Date**: YYYY-MM-DD

## ⚡ Trader's Bottom Line (TL;DR)
> [≤30 words: Current regime + Core action + Key defense]
**Confidence**: [🟢High/🟡Medium/🔴Low] — [One-line reason]

## 🎯 Today's Core Narrative [Lifecycle Label]
**[One-line thesis]**
| Dimension | Content |
|-----------|---------|
| **What Happened** | [Event description] |
| **Why It Matters** | [What expectations changed] |
| **Transmission Path** | [Asset A] → [Asset B] → [Asset C] |

## 📈 Key Data Dashboard
### Rates & Bonds
| Metric | Current | Daily Chg | Weekly Chg | Key Level |
|--------|---------|-----------|------------|-----------|
| 2Y Treasury | X.XX% | +Xbp | +Xbp | [Position] |
| 10Y Treasury | X.XX% | +Xbp | +Xbp | [Position] |
| 2s10s Spread | Xbp | +Xbp | - | [Curve Shape] |
| Real Rate (TIPS) | X.XX% | +Xbp | - | - |

### FX
| Pair | Current | Daily Chg | Weekly Chg | Key Level |
|------|---------|-----------|------------|-----------|
| DXY | XXX.XX | +X.X% | +X.X% | [Position] |
| USD/JPY | XXX.XX | +X.X% | +X.X% | [Position] |

### Commodities
| Asset | Current | Daily Chg | Weekly Chg | Key Level |
|-------|---------|-----------|------------|-----------|
| WTI Crude | $XX.XX | +X.X% | +X.X% | [Position] |
| Gold | $X,XXX | +X.X% | +X.X% | [Position] |
| Copper | $X.XX | +X.X% | +X.X% | [Position] |

### Risk Indicators
| Metric | Current | Daily Chg | Signal |
|--------|---------|-----------|--------|
| VIX | XX.XX | +X.X% | [Panic/Calm] |
| Copper/Gold Ratio | X.XX | +X.X% | [Economic Outlook] |

## 🔄 Cross-Asset Logic Validation
**Current Macro Regime**: [Regime Name] — [One-line description]
**Asset Direction Consistency Check**:
- ✅ [Consistent asset]: [Description]
- 🚨 [If divergence]: [Divergence description]

## 📋 Today's Watchlist (4-5 items)
1️⃣ **[Asset] [Level] Threshold**
   - Current: [Price], Distance to threshold [X%]
   - If [Trigger condition] → [Expected reaction]
   - If [Invalidation condition] → [Opposite expectation]
   - 💥 Pain Trade: [Crowded direction analysis]

## 📈 Trade Transmission Analysis | Confidence: [🟢/🟡/🔴]
### Bullish Logic Support (Tailwinds)
| Beneficiary Asset | Logic |
|-------------------|-------|
| [Asset 1] | [Reason] |

### Bearish Logic Support (Headwinds)
| Pressured Asset | Logic |
|-----------------|-------|
| [Asset 1] | [Reason] |

### 💥 Pain Trade Analysis
| Dimension | Content |
|-----------|---------|
| **Current Consensus Position** | [Description] |
| **Crowding Level** | [High/Medium/Low] |
| **Invalidation Condition** | [When consensus gets burned] |
| **Stampede Direction** | [Which direction blows up if invalidated] |

## ⚠️ Risk Alerts
### [Level Icon] [Risk Name]
| Dimension | Content |
|-----------|---------|
| **Trigger Condition** | [Specific description] |
| **Pricing Status** | [Unpriced/Partially priced/Fully priced] |
| **Hedge Cost** | [Cheap/Normal/Expensive] |

**Impact & Transmission**:
- **Direct Impact**: [First reaction]
- **Second-Order Transmission**: [Chain reaction]

**Response Recommendation**: [Specific tools and direction]

## 📚 Historical Playbook Reference (if applicable)
**Current Scenario**: [Description]
**Similar History**: [Event]
**Potential Replay**: [Projection]

---
*Data Sources: FRED API / Finnhub / WebSearch*
*Generated: YYYY-MM-DD HH:MM UTC*
*Disclaimer: This report is for reference only, not investment advice*
```

## Confidence Labels (Full Mode Mandatory)

| Label | Criteria | Recommendation |
|-------|----------|----------------|
| 🟢 High | Data confirms, no divergence | Normal position sizing |
| 🟡 Medium | Some noise | Reduce positions |
| 🔴 Low | Severe divergence | **Watch more, trade less** |

---

## Language Output Rules

**Automatically determine output language based on user input:**
- If user asks/triggers in Chinese → Output report in Chinese
- If user asks/triggers in English → Output report in English
- Technical terms (e.g., Bear Steepener, Goldilocks, Pain Trade) remain in English regardless of output language

---

## Key Constraints Summary

1. **Complete Causal Chain**: What happened → Why it matters → What it impacts
2. **No Empty Statements**: ❌"Market volatility" → ✅"VIX rose from 15 to 22, up 47%"
3. **Bidirectional Logic Required**: Every watchpoint must have trigger + invalidation scenarios
4. **Data Timeliness Labels**: Lag >1 trading day → Label `[Data lagged T-N]`
5. **Disclaimer Required**: Every report must end with disclaimer
6. **Stagflation Special Rules**: Must warn about 60/40 failure, must analyze Copper/Gold ratio
7. **VIX Divergence Detection**: Required even in Brief mode; if geopolitical event persists but VIX drops >10% → Label Priced-in
8. **No Data Hallucination**: Only cite raw numbers from input data sources; derived values (e.g., Breakeven inflation) must be labeled `[Derived: formula]`
9. **Calculation Consistency Check**: When citing spreads/ratios, must explicitly show calculation and verify sign; 2s10s = 10Y - 2Y, if 10Y < 2Y then negative (inverted); **Sign errors prohibited**
10. **Units Required**: Commodity prices must include units (e.g., Copper $X.XX/lb, Oil $XX/bbl)
11. **Closed Causal Loop**: Must use TIPS real rate, DXY, USD/JPY to build complete transmission path, not just descriptive concatenation
12. **Data Dashboard Mandatory Rules**: All values in the Key Data Dashboard must be copied directly from the `data/YYYY-MM-DD.json` file. Filling from memory or intermediate variables is prohibited. Specific field mappings:
    - 2Y Treasury → `fetched.fred.DGS2.current`
    - 10Y Treasury → `fetched.fred.DGS10.current`
    - 2s10s Spread → `calculated.spread_2s10s.value_bp`
    - Real Rate → `fetched.fred.DFII10.current`
    - Breakeven → `calculated.breakeven.value_pct`
    - VIX → `fetched.fred.VIXCLS.current`
    - DXY → `fetched.fred.DTWEXBGS.current`
    - USD/JPY → `fetched.fred.DEXJPUS.current`
    - WTI → `fetched.commodities.wti.current`
    - Gold → `fetched.commodities.gold.current`
    - Copper → `fetched.commodities.copper.current`
    - S&P 500 → `fetched.fred.SP500.current`
    - HY OAS → `fetched.fred.BAMLH0A0HYM2.current`

### Mandatory Data Population Process (MANDATORY)

**🔴 This is the core process to prevent data hallucination. Must be strictly followed:**

**Step 1: Read the Data File**
- After running the script, must use Read tool to read the `data/YYYY-MM-DD.json` file
- If the script also generated `data/YYYY-MM-DD-dashboard.md`, prefer using that pre-filled template

**Step 2: Copy Field by Field**
- Copy values one by one from the JSON file to the report tables
- For each value filled, must be able to point to its exact path in the JSON
- "Recalling" any value from context memory is prohibited

**Step 3: Self-Verification**
- After completion, must check item by item:
  - [ ] DGS2 value matches `fetched.fred.DGS2.current` exactly
  - [ ] DGS10 value matches `fetched.fred.DGS10.current` exactly
  - [ ] All calculated.* field values correctly referenced
  - [ ] Units labeled correctly (%, bp, $/bbl, $/oz, $/lb)

**⚠️ Violation Consequence**: If any value in the report doesn't match the JSON file, the entire report is invalid and must be regenerated.

**🔴 Absolutely Prohibited**:
- Prohibited from "recalling" values from context — must copy from JSON
- Prohibited from rounding or reformatting raw values
- Prohibited from filling data tables without reading the JSON file
- Prohibited from confusing fields (e.g., putting DGS10 value in DGS2 position)

---

## Quality Checklist

### Good vs Bad Examples

**Good Headlines (Recommended):**
- "📊 Daily Macro Strategy | 🔴 Stagflation — Oil at highs, stocks & bonds both down"
- "📊 Daily Macro Strategy | 🟢 Goldilocks — CPI below expectations, rate cut hopes rise"
- "📊 Daily Macro Strategy | ⚫ Recession — 10Y plunges 15bp, recession trade activated"

**Bad Headlines (Avoid):**
- "Today's Market Analysis" (Too generic, no regime label)
- "Macro Brief" (No core narrative)
- "Market Volatility Increases" (No specific data)

### Common Errors ❌

❌ **Data Hallucination**: "Recalling" values from memory instead of copying from JSON
❌ **Vague Statements**: "Market volatility increases" → Should write "VIX rose from 15 to 22, up 47%"
❌ **One-Way Logic**: Only writing trigger condition, missing invalidation condition
❌ **Sign Errors**: 2s10s spread calculation wrong (should be 10Y-2Y)
❌ **Missing Units**: Writing "Copper 5.8" instead of "Copper $5.8/lb"
❌ **Ignoring Timeliness**: Using lagged data without labeling [T-N]
❌ **Broken Causality**: Only describing phenomena without explaining "why it matters"
❌ **Ignoring Priced-in**: Geopolitical event persists but VIX drops >10%, not labeled as priced-in
❌ **Regime Mismatch**: Stocks & bonds both down but labeled Goldilocks
❌ **Empty Risk**: Risk alert without trigger condition or response recommendation

### Content Checklist (Checkable)

**Core Narrative:**
- [ ] Has clear one-line thesis
- [ ] Explains "why it matters"
- [ ] Has complete causal chain (happened → matters → impacts)
- [ ] Labels lifecycle [T+0/T+N/De-escalation]

**Data Dashboard (Full mode):**
- [ ] All values copied from JSON file
- [ ] DGS2 = `fetched.fred.DGS2.current`
- [ ] DGS10 = `fetched.fred.DGS10.current`
- [ ] Units labeled correctly (%, bp, $/bbl, $/oz, $/lb)
- [ ] Lagged data labeled [T-N]

**Watchlist:**
- [ ] Brief 3 items / Full 4-5 items
- [ ] Each has specific price level
- [ ] Each has bidirectional logic (trigger + invalidation)
- [ ] At least 1 linked to core narrative
- [ ] Full mode has Pain Trade analysis

**Risk Alerts:**
- [ ] Brief 1 item / Full 1-2 items
- [ ] Opposes core narrative
- [ ] Has trigger condition
- [ ] Assesses pricing status (Unpriced/Partial/Full)
- [ ] Has response recommendation

**Cross-Asset Consistency:**
- [ ] Divergences detected and labeled
- [ ] VIX vs risk event consistency checked
- [ ] Stagflation warns about 60/40 failure
- [ ] Full mode has Copper/Gold ratio analysis

### 5-Minute Final Check (Required Before Publishing)

1. **Core Narrative**: Can one sentence summarize today's thesis?
2. **Data Verification**: Spot-check DGS2, DGS10 match JSON?
3. **Bidirectional Logic**: Does each watchpoint have trigger + invalidation?
4. **Unit Check**: Do commodity prices have units?
5. **Timeliness Labels**: Is lagged data labeled [T-N]?
6. **Disclaimer**: Does report end with disclaimer?

After passing above checks, report can be published.

---

## Example Output

### Brief Mode

```markdown
# 📊 Daily Macro Strategy | 🔴 Stagflation
**Date**: 2024-03-15

---

## 🎯 Today's Core Narrative [T+0 Outbreak]

**Oil is today's master switch for all asset pricing.**

WTI broke below $70 overnight to $68.50, down 4.2% on the day. OPEC+ production increase expectations combined with weak China demand deteriorating supply-demand dynamics. Oil down → Inflation expectations down → Rate expectations down → USD under pressure.

---

## 📋 Today's Watchlist (3 items)

1️⃣ **WTI $68 Support**: Break below → Target $65, energy stocks crushed; Bounce to $70 → Short covering
2️⃣ **10Y Treasury 4.20%**: Break 4.25% → Growth stocks pressured; Return to 4.10% → Tech relief
3️⃣ **Tonight's CPI (8:30 PM ET)**: Expected 3.2%, >3.4% → Rate cuts off table, <3.0% → Risk rally

---

## ⚠️ Risk Alert

**Oil Rebound Risk** 🔴: Middle East escalation or OPEC+ price support → Oil V-shaped reversal, short squeeze | Pricing: Unpriced | Response: Avoid heavy short energy positions

---
*Generated: 2024-03-15 08:30 UTC*
*Disclaimer: For reference only, not investment advice*
```
