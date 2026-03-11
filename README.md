# Daily Macro Skill | 每日宏观数据分析

A Claude Code skill for daily macroeconomic data analysis and market briefings.

## Features

- **6 Core Analysis Modules**:
  - Fed Dynamics (美联储动态)
  - Commodities (大宗商品)
  - Treasury Rates (美债利率)
  - FX Markets (汇率市场)
  - Central Bank Watch (央行政策)
  - Breaking News (突发事件)

- **Enhanced Analytics**:
  - Expectation Gap Alerts (预期差预警)
  - Cross-Asset Divergence Detection (跨资产背离观察)
  - Trade Implication Framework (交易传导推演)
  - Historical Playbook (历史剧本复盘)

- **Flexible Data Sources**:
  - LSEG MCP (primary)
  - S&P Global MCP (secondary)
  - WebSearch (fallback)

## Installation

### Manual Installation

1. Clone this repository:
```bash
git clone https://github.com/christinaxu/daily-macro-skill.git
```

2. Copy to your Claude Code plugins directory:
```bash
mkdir ~/.claude/skills/
cp -r daily-macro-skill ~/.claude/skills/
```

## Usage

### Slash Command

```bash
/daily-macro           # Brief mode (default)
/daily-macro --brief   # Quick summary
/daily-macro --full    # Comprehensive report
```

### Natural Language Triggers

The skill also activates on these phrases:
- `每日宏观` / `daily macro`
- `今日市场` / `market overview`
- `宏观分析` / `macro briefing`
- `市场速览` / `宏观速报`

## Output Modes

### Brief Mode (`--brief`)
Quick summary with 2-3 sentences per section. Ideal for morning check-ins.

### Full Mode (`--full`)
Comprehensive report including:
- Detailed data tables
- Expectation gap analysis
- Cross-asset correlation checks
- Trade implications (Tailwinds/Headwinds/Pain Trade)
- Historical playbook for major events

## Sample Output

```markdown
# 📊 每日宏观速览 | Daily Macro Brief
**日期**: 2026-03-11

## 🏛️ Fed 动态
Fed 维持利率 5.25-5.50% 不变，市场预期 6 月降息概率升至 65%...

## 🛢️ 大宗商品
WTI 原油 $78.50 (+1.2%)，受中东局势影响...

## 📊 美债利率
10Y 收益率 4.25% (-3bp)，2s10s 利差 -15bp 维持倒挂...

## 💱 汇率市场
DXY 104.50 (-0.3%)，美元走弱受降息预期压制...

## 🏦 央行动态
ECB 本周四议息，市场预期维持不变...

## ⚡ 突发事件
无重大突发
```

## Configuration

### MCP Data Sources

If you have LSEG or S&P Global MCP servers configured, the skill will automatically use them. Otherwise, it falls back to WebSearch.

To configure MCP servers, add them to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "lseg": {
      "command": "...",
      "args": ["..."]
    },
    "spglobal": {
      "command": "...",
      "args": ["..."]
    }
  }
}
```

## Requirements

- Claude Code CLI
- Internet access (for WebSearch fallback)
- Optional: LSEG MCP, S&P Global MCP

## License

MIT License - see [LICENSE](LICENSE)

## Author

christinaxu

## Contributing

Issues and pull requests welcome at [GitHub](https://github.com/christinaxu/daily-macro-skill).
