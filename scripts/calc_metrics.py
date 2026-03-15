#!/usr/bin/env python3
"""
Daily Macro 数据获取 + 指标计算脚本

目标：
1) 真正拉取实时/最新可得数据（FRED + Finnhub/TwelveData 作为补充）
2) 输出“干净 JSON”（stdout 只打印 JSON；日志/告警走 stderr）
3) 输出结构与 daily-macro skill 文档一致：
   - calculated.spread_2s10s
   - calculated.curve_shape
   - calculated.breakeven
   - calculated.*_change
   - divergences (1-8 模式)

依赖：仅 Python 标准库（不需要 python-dotenv）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ---------------------------
# Small utilities
# ---------------------------


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _parse_iso_date(s: str) -> Optional[datetime]:
    try:
        # FRED uses YYYY-MM-DD
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _days_ago(ts_utc: datetime, obs_date_str: str) -> Optional[int]:
    d = _parse_iso_date(obs_date_str)
    if not d:
        return None
    return (ts_utc.date() - d.date()).days


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def calc_pct_change(current: float, previous: float) -> Dict[str, Any]:
    if previous == 0:
        return {"value_pct": None, "direction": None, "error": "previous is zero"}
    change = (current - previous) / previous * 100.0
    return {
        "value_pct": round(change, 2),
        "direction": "↑" if change > 0 else "↓" if change < 0 else "→",
    }


def calc_bp_change(current: float, previous: float) -> float:
    return round((current - previous) * 100.0, 1)


# ---------------------------
# .env loading (optional)
# ---------------------------


def load_env_file(path: Path) -> Dict[str, str]:
    """
    Minimal .env parser: KEY=VALUE, ignores blank lines and lines starting with '#'.
    Does not expand quotes/escapes; good enough for API keys.
    """
    out: Dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return out
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v:
                out[k] = v
    except Exception:
        return out
    return out


def load_default_env() -> None:
    """
    Load env vars from the skill repo if present:
    - <skill_root>/.env
    This keeps behavior consistent when running from anywhere.
    """
    # This file is intended to be copied into the skill repo as scripts/calc_metrics.py.
    # Here (workspace) we still load from the installed skill location if it exists.
    candidates = [
        # Running inside skill repo
        Path(__file__).resolve().parents[1] / ".env",
        # Installed location (per user's environment)
        Path.home() / ".claude" / "skills" / "daily-macro" / ".env",
    ]
    for p in candidates:
        env = load_env_file(p)
        if env:
            for k, v in env.items():
                os.environ.setdefault(k, v)
            return


# ---------------------------
# HTTP helpers
# ---------------------------


def http_get_json(url: str, timeout: float = 15.0, headers: Optional[Dict[str, str]] = None) -> Any:
    req = Request(url)
    req.add_header("User-Agent", "daily-macro-calc-metrics/1.2")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


# ---------------------------
# FRED fetch
# ---------------------------


@dataclass
class FredPoint:
    date: str
    value: float


def fetch_fred_points(series_id: str, api_key: str, limit: int = 20, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Fetch last N observations from FRED and return cleaned points (value != '.').
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(limit),
    }
    url = "https://api.stlouisfed.org/fred/series/observations?" + urlencode(params)
    try:
        data = http_get_json(url, timeout=timeout)
        obs = data.get("observations", []) or []
        points: List[Dict[str, Any]] = []
        for o in obs:
            v = o.get("value")
            if v in (None, ".", ""):
                continue
            fv = _safe_float(v)
            if fv is None:
                continue
            points.append({"date": o.get("date"), "value": fv})
        if not points:
            return {"series_id": series_id, "error": f"No valid data for {series_id}"}
        return {"series_id": series_id, "points": points}
    except HTTPError as e:
        return {"series_id": series_id, "error": f"HTTP {e.code}: {e.reason}"}
    except URLError as e:
        return {"series_id": series_id, "error": f"URL Error: {e.reason}"}
    except Exception as e:
        return {"series_id": series_id, "error": str(e)}


def summarize_fred_series(
    series_id: str,
    points_payload: Dict[str, Any],
    ts_utc: datetime,
    week_days: int = 7,
) -> Dict[str, Any]:
    """
    Convert points list into {current, previous, week_ago} snapshot.
    week_ago is chosen by:
    - first observation with date <= current_date - week_days
    - fallback: 5th valid observation if present
    """
    if "error" in points_payload:
        return points_payload

    points = points_payload.get("points", [])
    if not points:
        return {"series_id": series_id, "error": "No points"}

    cur = points[0]
    out: Dict[str, Any] = {
        "series_id": series_id,
        "current": cur["value"],
        "date": cur["date"],
    }
    if len(points) >= 2:
        prev = points[1]
        out["previous"] = prev["value"]
        out["previous_date"] = prev["date"]
    # week ago pick
    cur_dt = _parse_iso_date(cur["date"])
    if cur_dt:
        target = cur_dt - timedelta(days=week_days)
        week_pick = None
        for p in points:
            dt = _parse_iso_date(p["date"])
            if dt and dt.date() <= target.date():
                week_pick = p
                break
        if not week_pick and len(points) >= 6:
            week_pick = points[5]
        if week_pick:
            out["week_ago"] = week_pick["value"]
            out["week_ago_date"] = week_pick["date"]

    # freshness metadata
    da = _days_ago(ts_utc, cur["date"])
    if da is not None:
        out["days_ago"] = da
    return out


# ---------------------------
# Finnhub / Twelve Data fetch (commodities)
# ---------------------------


def fetch_finnhub_quote(symbol: str, token: str, timeout: float = 15.0) -> Dict[str, Any]:
    url = "https://finnhub.io/api/v1/quote?" + urlencode({"symbol": symbol, "token": token})
    try:
        data = http_get_json(url, timeout=timeout)
        # Finnhub returns: c=current, pc=previous close, d=change, dp=%change
        c = _safe_float(data.get("c"))
        pc = _safe_float(data.get("pc"))
        if c is None:
            return {"symbol": symbol, "error": "Missing current price (c)"}
        out: Dict[str, Any] = {"symbol": symbol, "current": c}
        if pc is not None:
            out["previous"] = pc
        # Keep raw fields for debugging
        out["raw"] = data
        return out
    except HTTPError as e:
        return {"symbol": symbol, "error": f"HTTP {e.code}: {e.reason}"}
    except URLError as e:
        return {"symbol": symbol, "error": f"URL Error: {e.reason}"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def fetch_twelvedata_quote(symbol: str, apikey: str, timeout: float = 15.0) -> Dict[str, Any]:
    url = "https://api.twelvedata.com/quote?" + urlencode({"symbol": symbol, "apikey": apikey})
    try:
        data = http_get_json(url, timeout=timeout)
        # TwelveData returns string fields; common ones: close, previous_close
        close = _safe_float(data.get("close"))
        prev = _safe_float(data.get("previous_close"))
        if close is None:
            # Some errors are JSON with "status":"error"
            msg = data.get("message") or "Missing close"
            return {"symbol": symbol, "error": msg, "raw": data}
        out: Dict[str, Any] = {"symbol": symbol, "current": close, "raw": data}
        if prev is not None:
            out["previous"] = prev
        return out
    except HTTPError as e:
        return {"symbol": symbol, "error": f"HTTP {e.code}: {e.reason}"}
    except URLError as e:
        return {"symbol": symbol, "error": f"URL Error: {e.reason}"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


# ---------------------------
# Stooq fetch (public, no key)
# ---------------------------


def _parse_stooq_csv_quote(text: str) -> Optional[Dict[str, str]]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    header = lines[0].split(",")
    row = lines[1].split(",")
    if len(header) != len(row):
        return None
    d = dict(zip(header, row))
    # Stooq uses "N/D" for missing
    if d.get("Close") in (None, "", "N/D"):
        return None
    return d


def fetch_stooq_quote(symbol: str, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Fetch Stooq snapshot quote as CSV and normalize.
    Note: for many futures symbols, Stooq does NOT provide previous close directly.
    We will return:
      - current: Close
      - previous: Open (intraday baseline) if available, with a warning flag
    """
    url = "https://stooq.com/q/l/?" + urlencode({"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"})
    try:
        req = Request(url)
        req.add_header("User-Agent", "daily-macro-calc-metrics/1.2")
        with urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode("utf-8", errors="replace")
        parsed = _parse_stooq_csv_quote(txt)
        if not parsed:
            return {"symbol": symbol, "error": "No data (N/D) from Stooq"}

        close = _safe_float(parsed.get("Close"))
        open_ = _safe_float(parsed.get("Open"))
        high = _safe_float(parsed.get("High"))
        low = _safe_float(parsed.get("Low"))
        date = parsed.get("Date")
        time_ = parsed.get("Time")
        if close is None:
            return {"symbol": symbol, "error": "Missing Close from Stooq"}

        out: Dict[str, Any] = {
            "symbol": symbol,
            "date": date,
            "time": time_,
            "current": close,
            "raw": parsed,
        }

        if open_ is not None and open_ != 0:
            out["previous"] = open_
            out["previous_kind"] = "open"  # not previous close
            out["warning"] = "Stooq snapshot does not provide previous close for this symbol; using today's open as baseline."

        if high is not None:
            out["high"] = high
        if low is not None:
            out["low"] = low
        return out
    except HTTPError as e:
        return {"symbol": symbol, "error": f"HTTP {e.code}: {e.reason}"}
    except URLError as e:
        return {"symbol": symbol, "error": f"URL Error: {e.reason}"}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


# ---------------------------
# Core calculations (aligned to skill docs)
# ---------------------------


def use_t10y2y(t10y2y: float) -> Dict[str, Any]:
    spread_bp = round(t10y2y * 100.0, 1)
    return {
        "value_bp": spread_bp,
        "is_inverted": spread_bp < 0,
        "label": "倒挂" if spread_bp < 0 else "正利差",
        "source": "FRED T10Y2Y (官方数据)",
    }


def calc_spread_from_rates(dgs10: float, dgs2: float) -> Dict[str, Any]:
    spread_pct = dgs10 - dgs2
    spread_bp = round(spread_pct * 100.0, 1)
    return {
        "value_bp": spread_bp,
        "is_inverted": spread_bp < 0,
        "label": "倒挂" if spread_bp < 0 else "正利差",
        "source": "Calculated from FRED DGS10 - DGS2 [fallback]",
        "warning": "⚠️ 使用了点位自行计算；优先建议使用 FRED T10Y2Y",
    }


def calc_curve_shape(dgs10: float, dgs10_prev: float, dgs2: float, dgs2_prev: float) -> Dict[str, Any]:
    chg_10y = dgs10 - dgs10_prev
    chg_2y = dgs2 - dgs2_prev
    spread_chg = chg_10y - chg_2y

    if chg_10y > 0 and chg_2y > 0:
        if chg_10y > chg_2y:
            shape = "Bear Steepener"
            driver = "10Y↑主导"
            meaning = "再通胀/过热，通胀预期上升"
        else:
            shape = "Bear Flattener"
            driver = "2Y↑主导"
            meaning = "Fed加息/重新定价短端"
    elif chg_10y < 0 and chg_2y < 0:
        if abs(chg_2y) > abs(chg_10y):
            shape = "Bull Steepener"
            driver = "2Y↓主导"
            meaning = "衰退/恐慌降息预期"
        else:
            shape = "Bull Flattener"
            driver = "10Y↓主导"
            meaning = "避险/增长担忧"
    else:
        if spread_chg > 0:
            shape = "Steepening"
            driver = "利差走阔"
            meaning = "需结合方向判断"
        else:
            shape = "Flattening"
            driver = "利差收窄"
            meaning = "需结合方向判断"

    return {
        "shape": shape,
        "driver": driver,
        "meaning": meaning,
        "chg_10y_bp": round(chg_10y * 100.0, 1),
        "chg_2y_bp": round(chg_2y * 100.0, 1),
        "spread_chg_bp": round(spread_chg * 100.0, 1),
    }


def calc_breakeven(dgs10: float, dfii10: float) -> Dict[str, Any]:
    breakeven = dgs10 - dfii10
    return {
        "value_pct": round(breakeven, 2),
        "source": "Derived [DGS10 - DFII10]",
        "formula": f"{dgs10}% - {dfii10}% = {round(breakeven, 2)}%",
    }


def calc_copper_gold_ratio(copper: float, gold: float) -> Dict[str, Any]:
    if gold == 0:
        return {"value": None, "error": "gold is zero"}
    ratio = copper / gold * 1000.0
    return {"value": round(ratio, 4), "note": "Cu/Au * 1000"}


def detect_divergences(m: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Implements 8 divergence patterns described in SKILL.md.
    Expects:
      - spx_chg_pct, vix_chg_pct, wti_chg_pct, copper_chg_pct, gold_chg_pct, dxy_chg_pct, usdjpy_chg_pct
      - dgs10_chg_bp, dfii10_chg_bp, hy_oas_chg_bp
      - copper_gold_ratio_chg_pct (optional)
      - vix_level (for mode 6 threshold)
    """
    divergences: List[Dict[str, Any]] = []

    spx = m.get("spx_chg_pct")
    vix = m.get("vix_chg_pct")
    wti = m.get("wti_chg_pct")
    copper = m.get("copper_chg_pct")
    gold = m.get("gold_chg_pct")
    dxy = m.get("dxy_chg_pct")
    usdjpy = m.get("usdjpy_chg_pct")
    dgs10_bp = m.get("dgs10_chg_bp")
    dfii10_bp = m.get("dfii10_chg_bp")
    hy_oas_bp = m.get("hy_oas_chg_bp")
    vix_level = m.get("vix_level")
    cg_ratio_chg = m.get("copper_gold_ratio_chg_pct")

    # Mode 1: real yield up + gold up
    if dfii10_bp is not None and gold is not None:
        if dfii10_bp > 5 and gold > 1:
            divergences.append(
                {
                    "pattern": 1,
                    "name": "实际利率背离",
                    "description": f"DFII10 +{dfii10_bp}bp 且 黄金 +{gold}%",
                    "severity": "⚠️ 趋势反转信号",
                }
            )

    # Mode 2: SPX up + VIX up
    if spx is not None and vix is not None:
        if spx > 0.5 and vix > 5:
            divergences.append(
                {
                    "pattern": 2,
                    "name": "期权异动",
                    "description": f"SPX +{spx}% 但 VIX +{vix}%",
                    "severity": "🔴 见顶前兆",
                }
            )

    # Mode 3: stagflation pricing (stocks down + yields up + commodities up)
    if spx is not None and dgs10_bp is not None:
        if spx < -1 and dgs10_bp > 5 and (
            (wti is not None and wti > 1.5) or (copper is not None and copper > 1.5)
        ):
            desc_bits = [f"SPX {spx}%", f"10Y +{dgs10_bp}bp"]
            if wti is not None:
                desc_bits.append(f"WTI {wti}%")
            if copper is not None:
                desc_bits.append(f"铜 {copper}%")
            divergences.append(
                {
                    "pattern": 3,
                    "name": "滞胀定价",
                    "description": " + ".join(desc_bits),
                    "severity": "🔴 极度危险",
                }
            )

    # Mode 4: recession confirmation (10Y down hard + gold up)
    if dgs10_bp is not None and gold is not None:
        if dgs10_bp < -10 and gold > 1.5:
            divergences.append(
                {
                    "pattern": 4,
                    "name": "衰退确认",
                    "description": f"10Y {dgs10_bp}bp 且 黄金 +{gold}%",
                    "severity": "⚠️ 衰退交易确认",
                }
            )

    # Mode 5: liquidity crisis (stocks down + gold down + yields up + HY OAS wider)
    if spx is not None and gold is not None and dgs10_bp is not None and hy_oas_bp is not None:
        if spx < -2 and gold < -1 and dgs10_bp > 5 and hy_oas_bp > 50:
            divergences.append(
                {
                    "pattern": 5,
                    "name": "流动性危机",
                    "description": "黄金↓ + 股市↓ + 收益率↑ + HY OAS飙升",
                    "severity": "☠️ 最高危",
                }
            )

    # Mode 6: carry unwind (USDJPY down big + SPX down + VIX high)
    if usdjpy is not None and vix_level is not None and spx is not None:
        if usdjpy < -1.5 and spx < -1 and vix_level > 20:
            vix_desc = f"VIX {vix_level}"
            vix_chg_desc = f"({vix}%)" if vix is not None else ""
            divergences.append(
                {
                    "pattern": 6,
                    "name": "套息平仓",
                    "description": f"USD/JPY {usdjpy}% + SPX {spx}% + {vix_desc}{vix_chg_desc}",
                    "severity": "🔴 连环爆仓预警",
                }
            )

    # Mode 7: copper/gold ratio down + 10Y up
    if cg_ratio_chg is not None and dgs10_bp is not None:
        if cg_ratio_chg < 0 and dgs10_bp > 0:
            divergences.append(
                {
                    "pattern": 7,
                    "name": "铜金比背离",
                    "description": f"铜金比 {cg_ratio_chg}% 且 10Y +{dgs10_bp}bp",
                    "severity": "🔍 寻机信号",
                }
            )

    # Mode 8: DXY up + gold up
    if dxy is not None and gold is not None:
        if dxy > 0.5 and gold > 1:
            divergences.append(
                {
                    "pattern": 8,
                    "name": "法币信用对冲",
                    "description": f"DXY +{dxy}% 且 黄金 +{gold}%",
                    "severity": "☠️ 极高危尾部风险",
                }
            )

    return divergences


def process_raw_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept normalized raw inputs and output calculated fields aligned to SKILL.md.
    """
    ts_utc = datetime.now(timezone.utc)
    result: Dict[str, Any] = {
        "timestamp": ts_utc.isoformat(),
        "input": raw,
        "calculated": {},
        "divergences": [],
        "warnings": [],
        "errors": [],
    }

    try:
        # 2s10s: prefer T10Y2Y (in percent)
        if raw.get("t10y2y") is not None:
            result["calculated"]["spread_2s10s"] = use_t10y2y(float(raw["t10y2y"]))
        elif raw.get("dgs10") is not None and raw.get("dgs2") is not None:
            result["calculated"]["spread_2s10s"] = calc_spread_from_rates(float(raw["dgs10"]), float(raw["dgs2"]))
            result["warnings"].append("Missing T10Y2Y; spread_2s10s computed from DGS10-DGS2 fallback.")

        # curve shape needs prevs
        if all(raw.get(k) is not None for k in ["dgs10", "dgs10_prev", "dgs2", "dgs2_prev"]):
            result["calculated"]["curve_shape"] = calc_curve_shape(
                float(raw["dgs10"]),
                float(raw["dgs10_prev"]),
                float(raw["dgs2"]),
                float(raw["dgs2_prev"]),
            )

        # breakeven: prefer T10YIE if provided, also provide derived cross-check if possible
        breakeven_block: Dict[str, Any] = {}
        if raw.get("t10yie") is not None:
            breakeven_block["value_pct"] = round(float(raw["t10yie"]), 2)
            breakeven_block["source"] = "FRED T10YIE (直接读取)"
        if raw.get("dgs10") is not None and raw.get("dfii10") is not None:
            derived = calc_breakeven(float(raw["dgs10"]), float(raw["dfii10"]))
            breakeven_block["derived"] = derived
            if "value_pct" in breakeven_block:
                diff_bp = round((breakeven_block["value_pct"] - derived["value_pct"]) * 100.0, 1)
                breakeven_block["cross_check_diff_bp"] = diff_bp
        if breakeven_block:
            result["calculated"]["breakeven"] = breakeven_block

        # copper/gold ratio
        if raw.get("copper") is not None and raw.get("gold") is not None and float(raw["gold"]) > 0:
            result["calculated"]["copper_gold_ratio"] = calc_copper_gold_ratio(float(raw["copper"]), float(raw["gold"]))

        # pct changes
        for asset in ["wti", "brent", "gold", "copper", "dxy", "spx", "vix", "usdjpy", "hy_oas", "dfii10", "dgs10"]:
            curr_key = asset
            prev_key = f"{asset}_prev"
            if raw.get(curr_key) is not None and raw.get(prev_key) is not None:
                curr = float(raw[curr_key])
                prev = float(raw[prev_key])
                if asset in ("dfii10", "dgs10", "hy_oas"):
                    result["calculated"][f"{asset}_change_bp"] = {"value_bp": calc_bp_change(curr, prev)}
                else:
                    result["calculated"][f"{asset}_change"] = calc_pct_change(curr, prev)

        # divergence detection inputs
        div_in: Dict[str, Any] = {
            "spx_chg_pct": result["calculated"].get("spx_change", {}).get("value_pct"),
            "vix_chg_pct": result["calculated"].get("vix_change", {}).get("value_pct"),
            "wti_chg_pct": result["calculated"].get("wti_change", {}).get("value_pct"),
            "copper_chg_pct": result["calculated"].get("copper_change", {}).get("value_pct"),
            "gold_chg_pct": result["calculated"].get("gold_change", {}).get("value_pct"),
            "dxy_chg_pct": result["calculated"].get("dxy_change", {}).get("value_pct"),
            "usdjpy_chg_pct": result["calculated"].get("usdjpy_change", {}).get("value_pct"),
            "dgs10_chg_bp": result["calculated"].get("dgs10_change_bp", {}).get("value_bp"),
            "dfii10_chg_bp": result["calculated"].get("dfii10_change_bp", {}).get("value_bp"),
            "hy_oas_chg_bp": result["calculated"].get("hy_oas_change_bp", {}).get("value_bp"),
            "vix_level": raw.get("vix"),
        }

        # copper/gold ratio change (if we have ratio and prev ratio)
        if raw.get("copper") is not None and raw.get("gold") is not None and raw.get("copper_prev") is not None and raw.get("gold_prev") is not None:
            try:
                r0 = float(raw["copper"]) / float(raw["gold"])
                r1 = float(raw["copper_prev"]) / float(raw["gold_prev"])
                if r1 != 0:
                    div_in["copper_gold_ratio_chg_pct"] = round((r0 - r1) / r1 * 100.0, 2)
            except Exception:
                pass

        result["divergences"] = detect_divergences(div_in)

    except Exception as e:
        result["errors"].append(str(e))

    return result


# ---------------------------
# Live data fetch + normalization
# ---------------------------


FRED_REQUIRED_SERIES = [
    # Rates / curve
    "DGS2",
    "DGS10",
    "DGS30",
    "T10Y2Y",
    "DFII10",
    "T10YIE",
    # Risk / credit
    "VIXCLS",
    "BAMLH0A0HYM2",
    # FX
    "DTWEXBGS",  # trade-weighted USD index (often incorrectly labeled "DXY")
    "DEXJPUS",   # USD/JPY
    "DEXUSEU",   # EUR/USD
    "DEXCHUS",   # USD/CNY
    # Equity / energy
    "SP500",
    "DCOILWTICO",
    "DCOILBRENTEU",
]


def fetch_live_data(
    fred_api_key: str,
    finnhub_api_key: Optional[str],
    twelvedata_api_key: Optional[str],
    timeout: float,
    quiet: bool,
) -> Dict[str, Any]:
    ts_utc = datetime.now(timezone.utc)
    fetched: Dict[str, Any] = {"timestamp": ts_utc.isoformat(), "fred": {}, "commodities": {}, "errors": [], "warnings": []}

    # Fetch FRED in parallel
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(fetch_fred_points, sid, fred_api_key, 25, timeout): sid for sid in FRED_REQUIRED_SERIES}
        for fut in as_completed(futs):
            sid = futs[fut]
            payload = fut.result()
            fetched["fred"][sid] = summarize_fred_series(sid, payload, ts_utc)

    # Commodities: prefer Finnhub quotes for (WTI/Brent/Gold/Copper). FRED oil series is daily & lagged.
    # NOTE:
    # - Finnhub /quote with symbols like CL/BZ/GC/HG frequently maps to EQUITY tickers (e.g. CL=Colgate),
    #   not commodities. So we DO NOT use Finnhub for commodities by default.
    # - Twelve Data is attempted for gold spot (XAU/USD). If blocked/unavailable, we fallback.
    # - Stooq is used as a public fallback for WTI/gold/copper snapshots.

    def _fetch_wti() -> Dict[str, Any]:
        q = fetch_stooq_quote("cl.f", timeout=timeout)
        return {"source": "Stooq", **q, "unit": "$/bbl"}

    def _fetch_gold() -> Dict[str, Any]:
        # Try Twelve Data first (requested)
        attempts: List[Dict[str, Any]] = []
        if twelvedata_api_key:
            q = fetch_twelvedata_quote("XAU/USD", twelvedata_api_key, timeout=timeout)
            if "error" not in q:
                return {"source": "TwelveData", **q, "unit": "$/oz", "attempts": attempts}
            # keep the error but still fall through
            attempts.append({"source": "TwelveData", "symbol": "XAU/USD", "error": q.get("error")})
        # Fallback: Stooq XAUUSD (has decent daily history, but we use snapshot here)
        q2 = fetch_stooq_quote("xauusd", timeout=timeout)
        return {"source": "Stooq", **q2, "unit": "$/oz", "attempts": attempts}

    def _fetch_copper() -> Dict[str, Any]:
        q = fetch_stooq_quote("hg.f", timeout=timeout)
        # Stooq HG.F often returns cents/lb (e.g. 587.7) -> normalize to $/lb.
        cur = _safe_float(q.get("current"))
        prev = _safe_float(q.get("previous"))
        if cur is not None and cur > 50:
            q["current"] = round(cur / 100.0, 4)
            if prev is not None:
                q["previous"] = round(prev / 100.0, 4)
            q["normalized_note"] = "Converted from cents/lb to $/lb"
        return {"source": "Stooq", **q, "unit": "$/lb"}

    # Brent: no reliable real-time public source configured; rely on FRED (lagged) in normalization step.
    def _fetch_brent() -> Dict[str, Any]:
        return {
            "source": None,
            "symbol": None,
            "warning": "Brent live quote not configured; will use FRED DCOILBRENTEU (lagged).",
        }

    commodity_fetchers = {
        "wti": _fetch_wti,
        "brent": _fetch_brent,
        "gold": _fetch_gold,
        "copper": _fetch_copper,
    }

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fn): name for name, fn in commodity_fetchers.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            fetched["commodities"][name] = fut.result()

    # Surface commodity warnings (baseline kind etc.)
    for name, q in (fetched.get("commodities") or {}).items():
        if isinstance(q, dict) and q.get("previous_kind") == "open":
            fetched["warnings"].append(f"{name} quote uses today's open as baseline (no previous close available from source).")

    # Freshness warnings for key FRED series
    for sid in ["DGS2", "DGS10", "VIXCLS", "DTWEXBGS", "DEXJPUS", "SP500"]:
        s = fetched["fred"].get(sid, {})
        if "date" in s and s.get("days_ago") is not None and s["days_ago"] > 1:
            fetched["warnings"].append(f"{sid} latest observation is {s['days_ago']} days old (date {s['date']}).")

    if fetched["fred"].get("DTWEXBGS", {}).get("series_id") == "DTWEXBGS":
        fetched["warnings"].append("DTWEXBGS is a trade-weighted USD index, not the ICE DXY index (naming mismatch in docs).")

    if not quiet:
        # optional debug logs to stderr, never stdout
        fred_errors = [sid for sid, v in fetched["fred"].items() if isinstance(v, dict) and "error" in v]
        comm_errors = [k for k, v in fetched["commodities"].items() if isinstance(v, dict) and "error" in v]
        if fred_errors:
            eprint("FRED errors:", ", ".join(fred_errors))
        if comm_errors:
            eprint("Commodity quote errors:", ", ".join(comm_errors))

    return fetched


def normalize_fetched_to_raw(fetched: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map fetched payload into the normalized raw input used by process_raw_data().
    """
    raw: Dict[str, Any] = {}
    fred = fetched.get("fred", {}) or {}
    com = fetched.get("commodities", {}) or {}

    def _fred_val(series_id: str, field: str) -> Optional[float]:
        s = fred.get(series_id, {}) or {}
        return _safe_float(s.get(field))

    # Rates
    raw["dgs2"] = _fred_val("DGS2", "current")
    raw["dgs2_prev"] = _fred_val("DGS2", "previous")
    raw["dgs10"] = _fred_val("DGS10", "current")
    raw["dgs10_prev"] = _fred_val("DGS10", "previous")
    raw["dfii10"] = _fred_val("DFII10", "current")
    raw["dfii10_prev"] = _fred_val("DFII10", "previous")
    raw["t10y2y"] = _fred_val("T10Y2Y", "current")
    raw["t10y2y_prev"] = _fred_val("T10Y2Y", "previous")
    raw["t10yie"] = _fred_val("T10YIE", "current")

    # Risk / credit
    raw["vix"] = _fred_val("VIXCLS", "current")
    raw["vix_prev"] = _fred_val("VIXCLS", "previous")
    raw["hy_oas"] = _fred_val("BAMLH0A0HYM2", "current")
    raw["hy_oas_prev"] = _fred_val("BAMLH0A0HYM2", "previous")

    # FX
    raw["dxy"] = _fred_val("DTWEXBGS", "current")
    raw["dxy_prev"] = _fred_val("DTWEXBGS", "previous")
    raw["usdjpy"] = _fred_val("DEXJPUS", "current")
    raw["usdjpy_prev"] = _fred_val("DEXJPUS", "previous")

    # Equity
    raw["spx"] = _fred_val("SP500", "current")
    raw["spx_prev"] = _fred_val("SP500", "previous")

    # Commodities: prefer Finnhub/TwelveData; if missing, fallback to FRED oil
    def _comm(name: str) -> Tuple[Optional[float], Optional[float]]:
        q = com.get(name, {}) or {}
        cur = _safe_float(q.get("current"))
        prev = _safe_float(q.get("previous"))
        return cur, prev

    wti_cur, wti_prev = _comm("wti")
    if wti_cur is None:
        wti_cur = _fred_val("DCOILWTICO", "current")
        wti_prev = _fred_val("DCOILWTICO", "previous")
    raw["wti"] = wti_cur
    raw["wti_prev"] = wti_prev

    brent_cur, brent_prev = _comm("brent")
    if brent_cur is None:
        brent_cur = _fred_val("DCOILBRENTEU", "current")
        brent_prev = _fred_val("DCOILBRENTEU", "previous")
    raw["brent"] = brent_cur
    raw["brent_prev"] = brent_prev

    gold_cur, gold_prev = _comm("gold")
    if gold_cur is None:
        # FRED LBMA gold fixing (daily, but may be lagged)
        gold_cur = _fred_val("GOLDAMGBD228NLBM", "current")
        gold_prev = _fred_val("GOLDAMGBD228NLBM", "previous")
    raw["gold"] = gold_cur
    raw["gold_prev"] = gold_prev

    copper_cur, copper_prev = _comm("copper")
    raw["copper"] = copper_cur
    raw["copper_prev"] = copper_prev

    return raw


# ---------------------------
# Backwards-compatible: fetch rates only
# ---------------------------


def fetch_treasury_rates_only(fred_api_key: str, timeout: float) -> Dict[str, Any]:
    ts_utc = datetime.now(timezone.utc)
    needed = ["DGS2", "DGS10", "T10Y2Y"]
    out: Dict[str, Any] = {"timestamp": ts_utc.isoformat(), "fred": {}}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fetch_fred_points, sid, fred_api_key, 10, timeout): sid for sid in needed}
        for fut in as_completed(futs):
            sid = futs[fut]
            payload = fut.result()
            out["fred"][sid] = summarize_fred_series(sid, payload, ts_utc)
    raw = normalize_fetched_to_raw({"fred": out["fred"], "commodities": {}})
    calc = process_raw_data(raw)
    # Keep legacy top-level fields for convenience
    legacy: Dict[str, Any] = {
        "timestamp": out["timestamp"],
        "dgs2": out["fred"].get("DGS2"),
        "dgs10": out["fred"].get("DGS10"),
        "t10y2y": out["fred"].get("T10Y2Y"),
        "calculated": calc.get("calculated", {}),
        "errors": calc.get("errors", []),
        "warnings": calc.get("warnings", []),
    }
    return legacy


# ---------------------------
# CLI
# ---------------------------


def _load_json_input(s: str) -> Dict[str, Any]:
    p = Path(s)
    if p.exists() and p.is_file():
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    return json.loads(s)


def cleanup_old_data_files(data_dir: Path, max_age_days: int = 3, quiet: bool = False) -> int:
    """
    Delete data files older than max_age_days.
    Removes both .json and -dashboard.md files.
    Returns the number of files deleted.
    """
    deleted = 0
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=max_age_days)

    try:
        for f in data_dir.iterdir():
            if not f.is_file():
                continue
            # Match patterns: YYYY-MM-DD.json or YYYY-MM-DD-dashboard.md
            name = f.name
            if name.endswith(".json") or name.endswith("-dashboard.md"):
                # Extract date from filename
                date_str = name.split(".")[0].replace("-dashboard", "")
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if file_date < cutoff:
                        f.unlink()
                        deleted += 1
                        if not quiet:
                            eprint(f"Cleaned up old file: {f.name}")
                except ValueError:
                    # Not a date-formatted filename, skip
                    continue
    except Exception as e:
        if not quiet:
            eprint(f"Error during cleanup: {e}")

    return deleted


def save_to_data_dir(payload: Dict[str, Any], quiet: bool = False) -> Optional[str]:
    """
    Save payload to data/ directory with timestamp filename.
    Returns the saved file path, or None if save failed.
    Also cleans up files older than 3 days.
    """
    try:
        # Determine data directory (sibling to scripts/)
        script_dir = Path(__file__).resolve().parent
        data_dir = script_dir.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old files before saving new data
        cleanup_old_data_files(data_dir, max_age_days=3, quiet=quiet)

        # Use current date as filename
        ts = datetime.now(timezone.utc)
        filename = f"{ts.strftime('%Y-%m-%d')}.json"
        filepath = data_dir / filename

        # Write JSON
        filepath.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        if not quiet:
            eprint(f"Data saved to: {filepath}")

        return str(filepath)
    except Exception as e:
        if not quiet:
            eprint(f"Failed to save data: {e}")
        return None


def generate_markdown_dashboard(payload: Dict[str, Any]) -> str:
    """
    生成预填充的 Markdown 数据仪表盘，LLM 只需复制粘贴。
    数据直接从 payload 中提取，确保数值准确无误。
    """
    fred = payload.get("fetched", {}).get("fred", {})
    comm = payload.get("fetched", {}).get("commodities", {})
    calc = payload.get("calculated", {})
    ts = payload.get("timestamp", datetime.now(timezone.utc).isoformat())

    # 安全取值函数
    def get_fred(series: str, field: str = "current") -> str:
        val = fred.get(series, {}).get(field)
        return f"{val}" if val is not None else "[N/A]"

    def get_fred_date(series: str) -> str:
        return fred.get(series, {}).get("date", "N/A")

    def get_calc_pct(key: str) -> str:
        val = calc.get(key, {}).get("value_pct")
        if val is None:
            return "[N/A]"
        sign = "+" if val > 0 else ""
        return f"{sign}{val}"

    def get_calc_bp(key: str) -> str:
        val = calc.get(key, {}).get("value_bp")
        if val is None:
            return "[N/A]"
        sign = "+" if val > 0 else ""
        return f"{sign}{val}"

    def get_comm(name: str, field: str = "current") -> str:
        val = comm.get(name, {}).get(field)
        return f"{val}" if val is not None else "[N/A]"

    # 曲线形态
    curve = calc.get("curve_shape", {})
    curve_shape = curve.get("shape", "N/A")
    curve_meaning = curve.get("meaning", "")
    curve_10y_bp = curve.get("chg_10y_bp", "N/A")
    curve_2y_bp = curve.get("chg_2y_bp", "N/A")

    # 利差
    spread = calc.get("spread_2s10s", {})
    spread_bp = spread.get("value_bp", "N/A")
    spread_label = spread.get("label", "")

    # Breakeven
    be = calc.get("breakeven", {})
    be_val = be.get("value_pct", "N/A")

    # 铜金比
    cg = calc.get("copper_gold_ratio", {})
    cg_val = cg.get("value", "N/A")

    # VIX 信号
    vix_val = _safe_float(get_fred("VIXCLS"))
    vix_signal = "恐慌" if vix_val and vix_val > 25 else "警惕" if vix_val and vix_val > 20 else "平静"

    # 生成 Markdown
    md = f"""## 📈 关键数据仪表盘

<!-- ⚠️ 以下数据由脚本自动生成，禁止手动修改数值 -->
<!-- 数据来源: data/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json -->
<!-- 生成时间: {ts} -->

### 利率与债券
| 指标 | 当前值 | 日变动 | 数据日期 | 备注 |
|------|--------|--------|----------|------|
| 美债2Y | {get_fred('DGS2')}% | {get_calc_bp('dgs10_change_bp')}bp | {get_fred_date('DGS2')} | |
| 美债10Y | {get_fred('DGS10')}% | {get_calc_bp('dgs10_change_bp')}bp | {get_fred_date('DGS10')} | |
| 美债30Y | {get_fred('DGS30')}% | - | {get_fred_date('DGS30')} | |
| 2s10s利差 | {spread_bp}bp | - | - | {spread_label} |
| 实际利率(TIPS) | {get_fred('DFII10')}% | {get_calc_bp('dfii10_change_bp')}bp | {get_fred_date('DFII10')} | |
| Breakeven通胀 | {be_val}% | - | - | [推导: 10Y-TIPS] |

### 汇率
| 货币对 | 当前值 | 日变动 | 数据日期 |
|--------|--------|--------|----------|
| DXY (TWI) | {get_fred('DTWEXBGS')} | {get_calc_pct('dxy_change')}% | {get_fred_date('DTWEXBGS')} |
| USD/JPY | {get_fred('DEXJPUS')} | {get_calc_pct('usdjpy_change')}% | {get_fred_date('DEXJPUS')} |
| EUR/USD | {get_fred('DEXUSEU')} | - | {get_fred_date('DEXUSEU')} |

### 大宗商品
| 品种 | 当前值 | 日变动 | 数据来源 |
|------|--------|--------|----------|
| WTI原油 | ${get_comm('wti')}/bbl | {get_calc_pct('wti_change')}% | {comm.get('wti', {}).get('source', 'N/A')} |
| 黄金 | ${get_comm('gold')}/oz | {get_calc_pct('gold_change')}% | {comm.get('gold', {}).get('source', 'N/A')} |
| 铜 | ${get_comm('copper')}/lb | {get_calc_pct('copper_change')}% | {comm.get('copper', {}).get('source', 'N/A')} |

### 风险指标
| 指标 | 当前值 | 日变动 | 信号 |
|------|--------|--------|------|
| VIX | {get_fred('VIXCLS')} | {get_calc_pct('vix_change')}% | {vix_signal} |
| HY OAS | {get_fred('BAMLH0A0HYM2')}% | {get_calc_bp('hy_oas_change_bp')}bp | |
| S&P 500 | {get_fred('SP500')} | {get_calc_pct('spx_change')}% | |
| 铜金比 | {cg_val} | - | [推导: Cu/Au×1000] |

### 曲线形态
**{curve_shape}** — {curve_meaning}
- 10Y变动: {curve_10y_bp}bp
- 2Y变动: {curve_2y_bp}bp

<!-- 以上数据由脚本自动生成，禁止手动修改 -->
"""
    return md


def save_markdown_dashboard(payload: Dict[str, Any], quiet: bool = False) -> Optional[str]:
    """
    Save pre-filled Markdown dashboard to data/ directory.
    Returns the saved file path, or None if save failed.
    """
    try:
        script_dir = Path(__file__).resolve().parent
        data_dir = script_dir.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc)
        filename = f"{ts.strftime('%Y-%m-%d')}-dashboard.md"
        filepath = data_dir / filename

        md_content = generate_markdown_dashboard(payload)
        filepath.write_text(md_content, encoding="utf-8")

        if not quiet:
            eprint(f"Markdown dashboard saved to: {filepath}")

        return str(filepath)
    except Exception as e:
        if not quiet:
            eprint(f"Failed to save Markdown dashboard: {e}")
        return None


def main(argv: Optional[List[str]] = None) -> int:
    load_default_env()

    parser = argparse.ArgumentParser(description="Fetch & calculate daily macro metrics (clean JSON output)")
    parser.add_argument("--input", "-i", type=str, help="JSON file path or JSON string (skip live fetch)")
    parser.add_argument("--fetch", action="store_true", help="Fetch live data for all key series (default if no --input/--demo)")
    parser.add_argument("--fetch-rates", action="store_true", help="Fetch treasury rates only (DGS2/DGS10/T10Y2Y)")
    parser.add_argument("--demo", action="store_true", help="Use built-in demo data (offline)")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout seconds")
    parser.add_argument("--quiet", action="store_true", help="Disable stderr debug logs")
    parser.add_argument("--compact", action="store_true", help="Compact JSON (no indentation)")
    parser.add_argument("--no-save", action="store_true", help="Do not save data to data/ directory")
    parser.add_argument("--markdown", action="store_true", help="Also generate pre-filled Markdown dashboard")
    parser.add_argument("--fred-api-key", type=str, default=None, help="FRED API key (or env FRED_API_KEY)")
    parser.add_argument("--finnhub-api-key", type=str, default=None, help="Finnhub API key (or env FINNHUB_API_KEY)")
    parser.add_argument("--twelve-api-key", type=str, default=None, help="TwelveData API key (or env TWELVE_DATA_API_KEY)")
    args = parser.parse_args(argv)

    fred_api_key = args.fred_api_key or os.environ.get("FRED_API_KEY")
    finnhub_api_key = args.finnhub_api_key or os.environ.get("FINNHUB_API_KEY")
    twelve_api_key = args.twelve_api_key or os.environ.get("TWELVE_DATA_API_KEY")

    if args.fetch_rates:
        if not fred_api_key:
            payload = {"error": "FRED_API_KEY not set"}
        else:
            payload = fetch_treasury_rates_only(fred_api_key, timeout=args.timeout)
        print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
        return 0

    if args.input:
        raw = _load_json_input(args.input)
        payload = process_raw_data(raw)
        print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
        return 0

    if args.demo:
        demo = {
            "dgs10": 4.15,
            "dgs10_prev": 4.12,
            "dgs2": 3.57,
            "dgs2_prev": 3.56,
            "t10y2y": 0.58,
            "t10y2y_prev": 0.56,
            "dfii10": 1.82,
            "dfii10_prev": 1.80,
            "t10yie": 2.33,
            "vix": 24.93,
            "vix_prev": 23.00,
            "dxy": 119.49,
            "dxy_prev": 119.00,
            "usdjpy": 157.64,
            "usdjpy_prev": 156.20,
            "wti": 89.71,
            "wti_prev": 92.49,
            "gold": 2950.0,
            "gold_prev": 2920.0,
            "copper": 4.29,
            "copper_prev": 4.34,
            "spx": 5250.0,
            "spx_prev": 5100.0,
            "hy_oas": 3.45,
            "hy_oas_prev": 3.30,
        }
        payload = process_raw_data(demo)
        print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
        return 0

    # Default: fetch live (consistent with SKILL.md which calls `python3 scripts/calc_metrics.py`)
    if not fred_api_key:
        payload = {"error": "FRED_API_KEY not set"}
        print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
        return 0

    fetched = fetch_live_data(
        fred_api_key=fred_api_key,
        finnhub_api_key=finnhub_api_key,
        twelvedata_api_key=twelve_api_key,
        timeout=args.timeout,
        quiet=args.quiet,
    )
    raw = normalize_fetched_to_raw(fetched)
    calc = process_raw_data(raw)
    # Merge fetched + calc into one payload to make the tool self-contained
    payload = {
        "timestamp": calc.get("timestamp"),
        "fetched": fetched,
        "input": raw,
        "calculated": calc.get("calculated"),
        "divergences": calc.get("divergences"),
        "warnings": (fetched.get("warnings") or []) + (calc.get("warnings") or []),
        "errors": (fetched.get("errors") or []) + (calc.get("errors") or []),
    }

    # Save to data/ directory unless --no-save
    if not args.no_save:
        save_to_data_dir(payload, quiet=args.quiet)
        # Also save Markdown dashboard if --markdown flag is set
        if args.markdown:
            save_markdown_dashboard(payload, quiet=args.quiet)

    print(json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
