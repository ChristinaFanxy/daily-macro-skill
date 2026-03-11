# Daily Macro Analysis Skill | 每日宏观数据分析

## Trigger Conditions | 触发条件

Activate this skill when user input matches any of:
- `每日宏观` / `daily macro` / `今日市场` / `宏观分析` / `macro briefing`
- `市场速览` / `market overview` / `宏观速报`
- `/daily-macro` command

## Parameters | 参数

- `--brief` : Quick summary mode (2-3 sentences per section)
- `--full` : Full report mode (detailed analysis + tables + trade implications)
- Default: `--brief` if no parameter specified

---

## Data Source Priority | 数据源优先级

1. **LSEG MCP** (if available) — Real-time market data
2. **S&P Global MCP** (if available) — Economic indicators and research
3. **WebSearch** (fallback) — News and public data sources

Auto-fallback: If MCP sources unavailable, use WebSearch without prompting user.

---

## Analysis Framework | 分析框架

### Section 1: Fed Dynamics | 美联储动态
**Data to collect:**
- Fed Funds Rate (current, expected path)
- Recent FOMC statements or minutes
- Fed officials' speeches (hawkish/dovish scoring)
- Dot plot changes (if recent meeting)
- Market-implied rate probabilities (CME FedWatch)

**Output format:**
```
## 🏛️ Fed 动态

**当前利率**: [X.XX%]
**市场预期**: [下次会议概率分布]
**官员表态**: [鹰派/鸽派倾向 + 关键引述]
**预期差**: [实际 vs 预期，标注偏离程度]
```

---

### Section 2: Commodities | 大宗商品
**Data to collect:**
- Crude Oil (WTI, Brent) — price, daily change, inventory data
- Gold (XAU) — price, daily change, ETF flows
- Copper — price, daily change (economic bellwether)
- Agricultural commodities (if significant moves)

**Output format:**
```
## 🛢️ 大宗商品

| 品种 | 价格 | 日涨跌 | 周涨跌 | 关键驱动 |
|------|------|--------|--------|----------|
| WTI原油 | $XX.XX | +X.X% | +X.X% | [驱动因素] |
| 布伦特 | $XX.XX | +X.X% | +X.X% | [驱动因素] |
| 黄金 | $X,XXX | +X.X% | +X.X% | [驱动因素] |
| 铜 | $X.XX | +X.X% | +X.X% | [驱动因素] |
```

---

### Section 3: Treasury Rates | 美债利率
**Data to collect:**
- US 2Y, 5Y, 10Y, 30Y yields
- 2s10s spread (yield curve)
- US-Japan 10Y spread
- US-Germany 10Y spread
- Real yields (TIPS)

**Output format:**
```
## 📊 美债利率

| 期限 | 收益率 | 日变动 | 周变动 |
|------|--------|--------|--------|
| 2Y | X.XX% | +Xbp | +Xbp |
| 10Y | X.XX% | +Xbp | +Xbp |
| 30Y | X.XX% | +Xbp | +Xbp |

**期限利差**:
- 2s10s: [Xbp] (曲线形态: 陡峭/平坦/倒挂)
- 美日10Y利差: [Xbp] (套息交易压力指标)
- 美德10Y利差: [Xbp]
```

---

### Section 4: FX Markets | 汇率市场
**Data to collect:**
- DXY (Dollar Index)
- EUR/USD, USD/JPY, GBP/USD, USD/CNY
- Emerging market currencies (if significant moves)

**Output format:**
```
## 💱 汇率市场

| 货币对 | 价格 | 日涨跌 | 周涨跌 | 关键驱动 |
|--------|------|--------|--------|----------|
| DXY | XXX.XX | +X.X% | +X.X% | [驱动因素] |
| EUR/USD | X.XXXX | +X.X% | +X.X% | [驱动因素] |
| USD/JPY | XXX.XX | +X.X% | +X.X% | [驱动因素] |
| USD/CNY | X.XXXX | +X.X% | +X.X% | [驱动因素] |
```

---

### Section 5: Central Bank Watch | 央行政策观察
**Data to collect:**
- ECB, BOJ, BOE, PBOC recent actions or statements
- Upcoming central bank meetings
- Policy divergence themes

**Output format:**
```
## 🏦 全球央行动态

**本周重点**:
- [央行名称]: [政策动态/声明摘要]

**即将到来的会议**:
- [日期] [央行] [市场预期]
```

---

### Section 6: Breaking News & Geopolitics | 突发事件与地缘政治
**Data to collect:**
- Geopolitical developments (wars, sanctions, elections)
- Major policy announcements
- Black swan events

**Output format:**
```
## ⚡ 突发事件与地缘政治

**[事件标题]**
- 事件概述: [简述]
- 市场影响: [受影响资产及方向]
- 历史参照: [类似事件的市场反应]
```

---

## Enhanced Features | 增强功能

### A. Expectation Gap Alert | 预期差预警系统

When actual data deviates from consensus by >1 standard deviation:

```
🚨 **[重大预期差预警]**

**数据**: [指标名称]
**预期**: [市场预期值]
**实际**: [实际值]
**偏离**: [X个标准差]
**历史影响**: [该类预期差通常利好/利空哪类资产]
```

---

### B. Cross-Asset Divergence Alert | 跨资产逻辑校验

Monitor classic correlations:
- US Treasury vs Gold (typically inverse)
- USD vs Non-USD currencies (typically inverse)
- Oil vs USD (typically inverse)
- Risk assets vs VIX (typically inverse)

When correlation breaks down:

```
⚠️ **[异常背离观察 (Divergence Alert)]**

**观察**: [资产A] 与 [资产B] 出现异常同向/反向运动
**历史相关性**: [正常情况下的关系]
**当前状态**: [描述背离]

**可能的底层逻辑**:
1. [假设1]
2. [假设2]
3. [假设3]
```

---

### C. Trade Implication Framework | 交易传导推演 (--full mode only)

```
## 📈 交易传导推演

### 多头逻辑支持 (Tailwinds)
- [受益资产/因子]: [原因]
- [受益资产/因子]: [原因]

### 空头逻辑支持 (Headwinds)
- [承压资产/因子]: [原因]
- [承压资产/因子]: [原因]

### 拥挤度与反身性 (Pain Trade)
- **主流仓位**: [描述当前市场共识仓位]
- **证伪条件**: [什么情况下共识会被打脸]
- **爆仓风险方向**: [如果证伪，哪个方向会出现踩踏]
```

---

### D. Historical Playbook | 历史剧本复盘

Trigger: Major breaking news OR significant data surprise

```
## 📚 历史剧本复盘

**触发事件**: [当前事件描述]

**相似历史事件**:

| 事件 | 日期 | 美债10Y | 标普500 | 黄金 | 美元指数 |
|------|------|---------|---------|------|----------|
| [事件1] | YYYY-MM | +Xbp | +X% | +X% | +X% |
| [事件2] | YYYY-MM | +Xbp | +X% | +X% | +X% |
| [事件3] | YYYY-MM | +Xbp | +X% | +X% | +X% |

*注: 数据为事件发生后一周内变动*

**本次可能的演绎路径**: [基于历史的推演]
```

---

## Output Template | 输出模板

### Brief Mode (--brief)

```markdown
# 📊 每日宏观速览 | Daily Macro Brief
**日期**: YYYY-MM-DD

[如有预期差预警，置于此处]

## 🏛️ Fed 动态
[2-3句摘要]

## 🛢️ 大宗商品
[2-3句摘要 + 关键价格]

## 📊 美债利率
[2-3句摘要 + 关键利率]

## 💱 汇率市场
[2-3句摘要 + DXY]

## 🏦 央行动态
[2-3句摘要]

## ⚡ 突发事件
[如有则列出，否则标注"无重大突发"]

---
*数据来源: [LSEG/S&P Global/WebSearch]*
*生成时间: YYYY-MM-DD HH:MM UTC*
```

### Full Mode (--full)

```markdown
# 📊 每日宏观分析报告 | Daily Macro Report
**日期**: YYYY-MM-DD

[如有预期差预警，置于此处]
[如有背离观察，置于此处]

## 🏛️ Fed 动态
[完整分析 + 数据表格]

## 🛢️ 大宗商品
[完整分析 + 数据表格]

## 📊 美债利率
[完整分析 + 数据表格 + 利差分析]

## 💱 汇率市场
[完整分析 + 数据表格]

## 🏦 央行动态
[完整分析 + 会议日历]

## ⚡ 突发事件
[完整分析 + 历史剧本复盘(如适用)]

## 📈 交易传导推演
[多头/空头/Pain Trade分析]

---
*数据来源: [LSEG/S&P Global/WebSearch]*
*生成时间: YYYY-MM-DD HH:MM UTC*
*免责声明: 本报告仅供参考，不构成投资建议*
```

---

## Execution Instructions | 执行指令

1. **Determine mode**: Check for `--brief` or `--full` parameter
2. **Check data sources**: Attempt LSEG MCP → S&P Global MCP → WebSearch
3. **Gather data**: Collect all 6 sections in parallel where possible
4. **Run checks**:
   - Scan for expectation gaps (>1 std dev from consensus)
   - Check cross-asset correlations for divergences
5. **Generate report**: Use appropriate template based on mode
6. **Add timestamps**: Include data source and generation time

---

## Error Handling | 错误处理

- If MCP unavailable: Silently fallback to WebSearch
- If data stale (>24h): Add warning banner at top of report
- If section data unavailable: Note "[数据暂不可用]" and continue with other sections
- If all sources fail: Inform user and suggest manual data check

---

## Language | 语言

- Default output language: 中文 (Chinese)
- If user query is in English: Output in English
- Mixed language acceptable for technical terms (e.g., "Fed", "DXY", "FOMC")
