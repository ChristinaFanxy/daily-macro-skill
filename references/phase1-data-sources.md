# PHASE 1: 数据获取 (Data Collection)

## 目录
- [1.1 数据源配置](#11-数据源配置)
- [1.2 FRED API](#12-fred-api)
- [1.3 Finnhub API](#13-finnhub-api)
- [1.4 Twelve Data API](#14-twelve-data-api)
- [1.5 Alpha Vantage API](#15-alpha-vantage-api)
- [1.6 数据质量校验](#16-数据质量校验)
- [1.7 Fallback 逻辑](#17-fallback-逻辑)

---

## 1.1 数据源配置

**API Keys (从环境变量读取):**
```
FRED_API_KEY, FINNHUB_API_KEY, TWELVE_DATA_API_KEY
ALPHA_VANTAGE_KEY_1, ALPHA_VANTAGE_KEY_2
```

**数据源分工 (优先级从左到右):**

| 数据类型 | 主数据源 | 备用1 | 备用2 |
|----------|----------|-------|-------|
| 美债收益率 | FRED | - | WebSearch |
| VIX | FRED | Finnhub | WebSearch |
| 汇率 (DXY, 主要货币对) | FRED | Twelve Data | WebSearch |
| **WTI/布伦特原油** | **Stooq (WTI) / FRED (Brent, 滞后)** | WebSearch | - |
| 黄金/铜 | Twelve Data (Gold: XAU/USD) / Stooq (Copper) | WebSearch | - |
| 标普500 | FRED | Finnhub | - |

**注意**: 新闻获取在 Phase 2 核心矛盾识别时进行，详见 [phase2-core-narrative.md](phase2-core-narrative.md)。

---

## 1.2 FRED API

**Base URL:** `https://api.stlouisfed.org/fred/series/observations`

**调用模板:**
```bash
curl -s "https://api.stlouisfed.org/fred/series/observations?series_id={SERIES_ID}&api_key=$FRED_API_KEY&file_type=json&limit=10&sort_order=desc"
```

**必须获取的 Series:**

| 批次 | Series ID | 数据名称 | 重要性 |
|------|-----------|----------|--------|
| **批次1: 利率** ||||
| | DGS2 | 2年期美债 | ⭐⭐⭐⭐⭐ |
| | DGS10 | 10年期美债 | ⭐⭐⭐⭐⭐ |
| | **T10Y2Y** | **2s10s利差 (直接读取，禁止自行计算)** | ⭐⭐⭐⭐⭐ |
| | DGS30 | 30年期美债 | ⭐⭐⭐⭐ |
| | DFII10 | 10年期TIPS(实际利率) | ⭐⭐⭐⭐ |
| | T10YIE | Breakeven通胀预期 (直接读取) | ⭐⭐⭐⭐ |
| | VIXCLS | VIX恐慌指数 | ⭐⭐⭐⭐⭐ |
| | BAMLH0A0HYM2 | HY OAS (高收益债利差) | ⭐⭐⭐⭐⭐ |
| **批次2: 汇率** ||||
| | DTWEXBGS | 美元指数DXY | ⭐⭐⭐⭐⭐ |
| | DEXJPUS | USD/JPY | ⭐⭐⭐⭐⭐ |
| | DEXUSEU | EUR/USD | ⭐⭐⭐⭐ |
| | DEXCHUS | USD/CNY | ⭐⭐⭐⭐ |
| **批次3: 商品&股指** ||||
| | DCOILWTICO | WTI原油 | ⭐⭐⭐⭐⭐ |
| | DCOILBRENTEU | 布伦特原油 | ⭐⭐⭐⭐ |
| | SP500 | 标普500 | ⭐⭐⭐⭐ |

**执行策略:** 三个批次并行发起，超时15秒，失败重试1次

---

## 1.3 Finnhub API

**Base URL:** `https://finnhub.io/api/v1`

⚠️ 注意: Finnhub 的 `/quote` 接口在不少账号/权限下对商品 symbol（如 `CL`/`BZ`/`GC`/`HG`）可能出现
ticker 冲突（映射到股票）或返回 0，容易造成口径错误。当前 `calc_metrics.py` 默认不使用 Finnhub 获取商品价格，
仅建议用于新闻或其他资产。

**商品报价:**
```bash
curl -s "https://finnhub.io/api/v1/quote?symbol={SYMBOL}&token=$FINNHUB_API_KEY"
```

**（不推荐）商品代码（易与股票 ticker 冲突）:**
- 历史文档中常见的 `CL`/`BZ`/`GC`/`HG` 在 Finnhub `/quote` 下可能不代表商品。
- 建议改用：WTI=Stooq `cl.f`；Copper=Stooq `hg.f`（脚本会从 cents/lb 转成 $/lb）；Gold=Twelve Data `XAU/USD`；Brent=FRED `DCOILBRENTEU`（滞后）。

**返回格式:**
```json
{"c": 85.50, "d": 1.25, "dp": 1.48, "pc": 84.25}
// c=当前价, d=涨跌额, dp=涨跌%, pc=前收
```

**新闻:**
```bash
curl -s "https://finnhub.io/api/v1/news?category=general&token=$FINNHUB_API_KEY"
```

---

## 1.4 Twelve Data API

**Base URL:** `https://api.twelvedata.com`

```bash
curl -s "https://api.twelvedata.com/quote?symbol={SYMBOL}&apikey=$TWELVE_DATA_API_KEY"
```

**商品代码:** XAU/USD (黄金)

---

## 1.5 Alpha Vantage API

**Base URL:** `https://www.alphavantage.co/query`

**贵金属:**
```bash
curl -s "https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=XAU&to_currency=USD&apikey=$ALPHA_VANTAGE_KEY_1"
```

**Key轮换:** KEY_1 超限 → 切换 KEY_2 → 都超限则用 Finnhub

---

## 1.6 数据质量校验

**新鲜度检查:**
| 情况 | 处理 |
|------|------|
| 今日或前一交易日 | ✅ 正常使用 |
| 2-3个交易日前 | ⚠️ 标注 `[数据滞后 T-N]` |
| >3个交易日前 | ❌ 标注 `[数据过期]`，触发fallback |

**异常值检测:**
| 资产 | 阈值 | 处理 |
|------|------|------|
| 美债10Y | >20bp | 标注 `[异常波动]`，需解释 |
| 黄金 | >3% | 标注 `[异常波动]` |
| 油价 | >5% | 标注 `[异常波动]` |
| VIX | >20% | 标注 `[异常波动]` |

**计算公式:**
- 日涨跌: (T0 - T-1) / T-1 × 100
- 2s10s利差: DGS10 - DGS2 (bp)
- 实际利率: DFII10 直接读取

---

## 1.7 Fallback 逻辑

```
FRED失败 → Finnhub/Twelve Data → WebSearch → 标注[数据暂不可用]
```

**部分数据缺失处理:**
| 缺失 | 替代方案 |
|------|----------|
| 黄金 | 用 VIX + 美债判断避险情绪 |
| VIX | 用 黄金 + 日元判断恐慌 |
| 美债收益率 | 必须通过WebSearch获取，否则报告降级 |

**全部失败:** 告知用户"数据源暂不可用"，不生成报告
