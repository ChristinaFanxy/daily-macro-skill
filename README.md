# Daily Macro Skill | 每日宏观策略分析

A Claude Code skill for daily macro strategy analysis. Not just data aggregation — it identifies core narratives, validates cross-asset logic, and generates actionable watchlists.

## Features

- **Core Narrative Identification**: Priority-based decision tree (Geopolitical → Central Bank → Data → Commodity → Technical → Routine)
- **Cross-Asset Validation**: 8 divergence patterns with danger levels (Carry Unwind, Liquidity Crisis, Stagflation, etc.)
- **4 Macro Regimes**: Goldilocks / Reflation / Stagflation / Recession with automatic detection
- **Actionable Watchlists**: Specific price levels with trigger + invalidation conditions
- **Pain Trade Analysis**: Crowded positioning and stampede direction (Full mode)

## Data Sources

| Data Type | Source | Status |
|-----------|--------|--------|
| Treasury Yields, VIX, DXY | FRED API | ✅ Real-time |
| Commodities (Oil, Gold, Copper) | Twelve Data / Alpha Vantage | ✅ Real-time |
| Economic Calendar (CPI, NFP, GDP) | Local JSON (BLS/Fed/BEA verified) | ✅ Verified |
| Central Bank Calendar | Local JSON (Fed verified) | ✅ Verified |
| Mag7 Earnings | Finnhub API | ✅ Free tier |
| Market News | NewsAPI | ⚠️ Optional |

## Installation

```bash
git clone https://github.com/ChristinaFanxy/daily-macro-skill.git ~/.claude/skills/daily-macro
cd ~/.claude/skills/daily-macro
cp .env.example .env
# Edit .env with your API keys
```

### Required API Keys

```bash
FRED_API_KEY=xxx        # https://fred.stlouisfed.org/docs/api/api_key.html
TWELVE_DATA_API_KEY=xxx # https://twelvedata.com/
ALPHA_VANTAGE_KEY_1=xxx # https://www.alphavantage.co/
```

### Optional API Keys

```bash
FINNHUB_API_KEY=xxx     # For Mag7 earnings calendar
NEWSAPI_KEY=xxx         # For market news
```

## Usage

### Slash Command

```bash
/daily-macro           # Brief mode (default)
/daily-macro --brief   # Core narrative + 3 watchpoints + 1 risk
/daily-macro --full    # Full report with data dashboard, pain trade, historical playbook
```

### Natural Language Triggers

- `每日宏观` / `daily macro` / `macro`
- `今日市场` / `market overview`
- `宏观分析` / `macro briefing`

## Output Modes

### Brief Mode (Default)
- Core narrative with lifecycle label
- 3 watchpoints with bidirectional logic
- 1 risk alert with pricing status

### Full Mode
- TL;DR with confidence level
- Key data dashboard (Rates, FX, Commodities, Risk indicators)
- Cross-asset logic validation
- 4-5 watchpoints with pain trade analysis
- Trade transmission (Tailwinds/Headwinds)
- Historical playbook reference

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/calc_metrics.py` | Fetch market data and calculate metrics |
| `scripts/fetch_macro_intel.py` | Fetch calendars and news |
| `scripts/validate_report.py` | Validate report data consistency |
| `scripts/daily_push.py` | Push report to Telegram (optional) |

## Project Structure

```
daily-macro/
├── SKILL.md              # English skill definition
├── SKILL-CN.md           # Chinese skill definition
├── scripts/              # Data fetching and validation
├── references/           # Calendars and methodology docs
│   ├── economic_calendar.json
│   ├── central_bank_calendar.json
│   ├── bls.ics
│   └── phase1-6 methodology docs
└── data/                 # Generated data files (gitignored)
```

## License

MIT License - see [LICENSE](LICENSE)

## Author

christinaxu

## Contributing

Issues and PRs welcome at [GitHub](https://github.com/ChristinaFanxy/daily-macro-skill).
