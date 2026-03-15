#!/usr/bin/env python3
"""
宏观信息获取脚本 - 经济日历、财报日历、央行日历、市场新闻

输出干净 JSON (stdout)，日志走 stderr。
依赖：仅 Python 标准库
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ---------------------------
# Utilities (复用 calc_metrics.py 模式)
# ---------------------------

def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def load_env_file(path: Path) -> Dict[str, str]:
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
        pass
    return out


def load_default_env() -> None:
    candidates = [
        Path(__file__).resolve().parents[1] / ".env",
        Path.home() / ".claude" / "skills" / "daily-macro" / ".env",
    ]
    for p in candidates:
        env = load_env_file(p)
        if env:
            for k, v in env.items():
                os.environ.setdefault(k, v)
            return


def http_get_json(url: str, timeout: float = 15.0, headers: Optional[Dict[str, str]] = None) -> Any:
    req = Request(url)
    req.add_header("User-Agent", "daily-macro-intel/1.0")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)


# ---------------------------
# 经济日历 (本地配置文件)
# ---------------------------

def load_economic_calendar(days: int = 7) -> Dict[str, Any]:
    """从本地配置加载经济日历"""
    calendar_path = Path(__file__).resolve().parents[1] / "references" / "economic_calendar.json"

    if not calendar_path.exists():
        return {"error": f"Calendar file not found: {calendar_path}", "events": []}

    try:
        with open(calendar_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        today = datetime.now(timezone.utc).date()
        cutoff = today + timedelta(days=days)

        events = []
        for ev in data.get("scheduled_events", []):
            event_date_str = ev.get("date", "")
            try:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            if today <= event_date <= cutoff:
                events.append({
                    "date": event_date_str,
                    "time": ev.get("time", ""),
                    "country": ev.get("country", ""),
                    "event": ev.get("event", ""),
                    "importance": ev.get("importance", "unknown"),
                    "note": ev.get("note"),
                    "forecast": None,
                    "previous": None,
                    "actual": None,
                })

        events.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
        return {
            "events": events,
            "count": len(events),
            "last_updated": data.get("last_updated"),
            "source": "local_config",
        }

    except Exception as e:
        return {"error": str(e), "events": []}

    except HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "events": []}
    except URLError as e:
        return {"error": f"URL Error: {e.reason}", "events": []}
    except Exception as e:
        return {"error": str(e), "events": []}


# ---------------------------
# Mag7 财报日历 (Finnhub)
# ---------------------------

MAG7_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]


def fetch_earnings_calendar(token: str, days: int = 30) -> Dict[str, Any]:
    """获取 Mag7 未来N天财报日期"""
    today = datetime.now(timezone.utc).date()
    from_date = today.isoformat()
    to_date = (today + timedelta(days=days)).isoformat()

    url = "https://finnhub.io/api/v1/calendar/earnings?" + urlencode({
        "from": from_date,
        "to": to_date,
        "token": token,
    })

    try:
        data = http_get_json(url)
        all_earnings = data.get("earningsCalendar", []) or []

        mag7_earnings = []
        for ev in all_earnings:
            symbol = ev.get("symbol", "")
            if symbol in MAG7_SYMBOLS:
                mag7_earnings.append({
                    "symbol": symbol,
                    "date": ev.get("date"),
                    "quarter": f"Q{ev.get('quarter', '?')} {ev.get('year', '')}",
                    "eps_estimate": ev.get("epsEstimate"),
                    "eps_actual": ev.get("epsActual"),
                    "revenue_estimate": ev.get("revenueEstimate"),
                })

        mag7_earnings.sort(key=lambda x: x.get("date", ""))
        return {"earnings": mag7_earnings, "count": len(mag7_earnings)}

    except HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "earnings": []}
    except URLError as e:
        return {"error": f"URL Error: {e.reason}", "earnings": []}
    except Exception as e:
        return {"error": str(e), "earnings": []}


# ---------------------------
# 央行日历 (本地配置)
# ---------------------------

def load_central_bank_calendar(days: int = 30) -> Dict[str, Any]:
    """从本地配置加载央行会议日历"""
    calendar_path = Path(__file__).resolve().parents[1] / "references" / "central_bank_calendar.json"

    if not calendar_path.exists():
        return {"error": f"Calendar file not found: {calendar_path}", "meetings": []}

    try:
        with open(calendar_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        today = datetime.now(timezone.utc).date()
        cutoff = today + timedelta(days=days)

        meetings = []
        for bank_key in ["fomc", "boj", "ecb"]:
            bank_data = data.get(bank_key, {})
            bank_name = bank_data.get("name", bank_key.upper())
            current_rate = bank_data.get("current_rate", "N/A")

            for meeting in bank_data.get("meetings", []):
                meeting_date_str = meeting.get("date", "")
                try:
                    meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue

                if today <= meeting_date <= cutoff:
                    entry = {
                        "date": meeting_date_str,
                        "bank": bank_key.upper(),
                        "bank_name": bank_name,
                        "event": "Rate Decision",
                        "current_rate": current_rate,
                    }
                    if meeting.get("has_projections"):
                        entry["note"] = "With economic projections"
                    if meeting.get("has_outlook"):
                        entry["note"] = "With outlook report"
                    meetings.append(entry)

        meetings.sort(key=lambda x: x.get("date", ""))
        return {
            "meetings": meetings,
            "count": len(meetings),
            "last_updated": data.get("last_updated"),
        }

    except Exception as e:
        return {"error": str(e), "meetings": []}


# ---------------------------
# 市场新闻 (NewsAPI)
# ---------------------------

NEWS_QUERIES = {
    "geopolitical": "war OR attack OR sanctions OR Iran OR Russia OR China tariff",
    "central_bank": "Federal Reserve OR Powell OR FOMC OR BOJ OR ECB OR Lagarde",
    "economic": "CPI OR inflation OR jobs report OR GDP OR unemployment",
}


def fetch_news_category(api_key: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """获取单个类别的新闻"""
    url = "https://newsapi.org/v2/everything?" + urlencode({
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": limit,
        "apiKey": api_key,
    })

    try:
        data = http_get_json(url)
        articles = data.get("articles", []) or []

        results = []
        for art in articles[:limit]:
            results.append({
                "title": art.get("title"),
                "source": art.get("source", {}).get("name"),
                "published_at": art.get("publishedAt"),
                "url": art.get("url"),
                "description": art.get("description"),
            })
        return results

    except Exception as e:
        return [{"error": str(e)}]


def fetch_all_news(api_key: str, limit: int = 5) -> Dict[str, Any]:
    """并发获取所有类别新闻"""
    if not api_key:
        return {
            "error": "NEWSAPI_KEY not configured",
            "geopolitical": [],
            "central_bank": [],
            "economic": [],
        }

    results: Dict[str, List[Dict[str, Any]]] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_news_category, api_key, query, limit): category
            for category, query in NEWS_QUERIES.items()
        }

        for future in as_completed(futures):
            category = futures[future]
            try:
                results[category] = future.result()
            except Exception as e:
                results[category] = [{"error": str(e)}]

    return results


# ---------------------------
# 数据保存 (复用 calc_metrics.py 模式)
# ---------------------------

def save_intel_data(data: Dict[str, Any], quiet: bool = False) -> Optional[Path]:
    """保存数据到 data/ 目录，自动清理3天前的文件"""
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(exist_ok=True)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = data_dir / f"{today_str}-intel.json"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if not quiet:
            eprint(f"[INFO] Saved to {out_path}")

        # 清理旧文件
        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        for old_file in data_dir.glob("*-intel.json"):
            try:
                date_part = old_file.stem.replace("-intel", "")
                file_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date < cutoff:
                    old_file.unlink()
                    if not quiet:
                        eprint(f"[INFO] Cleaned up old file: {old_file.name}")
            except (ValueError, OSError):
                pass

        return out_path

    except Exception as e:
        eprint(f"[ERROR] Failed to save: {e}")
        return None


# ---------------------------
# Main
# ---------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch macro intelligence data")
    parser.add_argument("--days", type=int, default=7, help="Calendar range in days (default: 7)")
    parser.add_argument("--news-limit", type=int, default=5, help="News articles per category (default: 5)")
    parser.add_argument("--no-save", action="store_true", help="Don't save to file")
    parser.add_argument("--quiet", action="store_true", help="Suppress stderr logs")
    args = parser.parse_args()

    load_default_env()

    finnhub_token = os.environ.get("FINNHUB_API_KEY", "")
    newsapi_key = os.environ.get("NEWSAPI_KEY", "")

    warnings: List[str] = []
    errors: List[str] = []

    if not finnhub_token:
        warnings.append("FINNHUB_API_KEY not set - earnings calendar will be empty")
    if not newsapi_key:
        warnings.append("NEWSAPI_KEY not set - news will be empty")

    if not args.quiet:
        eprint("[INFO] Fetching macro intelligence...")

    # 并发获取数据
    economic_cal: Dict[str, Any] = {}
    earnings_cal: Dict[str, Any] = {}
    central_bank_cal: Dict[str, Any] = {}
    news_data: Dict[str, Any] = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}

        # 经济日历使用本地配置
        futures[executor.submit(load_economic_calendar, args.days)] = "economic"

        if finnhub_token:
            futures[executor.submit(fetch_earnings_calendar, finnhub_token, 30)] = "earnings"

        futures[executor.submit(load_central_bank_calendar, args.days)] = "central_bank"
        futures[executor.submit(fetch_all_news, newsapi_key, args.news_limit)] = "news"

        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
                if key == "economic":
                    economic_cal = result
                elif key == "earnings":
                    earnings_cal = result
                elif key == "central_bank":
                    central_bank_cal = result
                elif key == "news":
                    news_data = result

                if result.get("error"):
                    errors.append(f"{key}: {result['error']}")
            except Exception as e:
                errors.append(f"{key}: {e}")

    # 构建输出
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "economic_calendar": economic_cal.get("events", []),
        "earnings_calendar": earnings_cal.get("earnings", []),
        "central_bank_calendar": central_bank_cal.get("meetings", []),
        "news": {
            "geopolitical": news_data.get("geopolitical", []),
            "central_bank": news_data.get("central_bank", []),
            "economic": news_data.get("economic", []),
        },
        "warnings": warnings,
        "errors": errors,
    }

    # 保存文件
    if not args.no_save:
        save_intel_data(output, args.quiet)

    # 输出 JSON
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
