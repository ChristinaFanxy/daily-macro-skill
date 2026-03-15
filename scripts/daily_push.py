#!/usr/bin/env python3
"""
Daily Macro Report Generator & Telegram Push
Generates macro strategy report and pushes to Telegram
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
import requests

# Configuration
SKILL_DIR = Path("/Users/christinaxu/.claude/skills/daily-macro")
DATA_DIR = SKILL_DIR / "data"
LOG_DIR = SKILL_DIR / "logs"
TG_BOT_TOKEN = "8268782703:AAFAZpL0NWQcN916QmvDzUonxPOqSKdSCss"
TG_CHAT_ID = "5118958859"

def log(msg: str):
    """Log message with timestamp"""
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}\n"
    print(log_line, end="")
    with open(LOG_DIR / "daily_push.log", "a") as f:
        f.write(log_line)

def send_telegram(text: str) -> bool:
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        return resp.json().get("ok", False)
    except Exception as e:
        log(f"Telegram send failed: {e}")
        return False

def fetch_data() -> dict:
    """Run calc_metrics.py and return data"""
    os.chdir(SKILL_DIR)
    result = subprocess.run(
        [sys.executable, "scripts/calc_metrics.py"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        log(f"Data fetch failed: {result.stderr}")
        return None

    # Read today's data file
    today = datetime.now().strftime("%Y-%m-%d")
    data_file = DATA_DIR / f"{today}.json"
    if not data_file.exists():
        log(f"Data file not found: {data_file}")
        return None

    with open(data_file) as f:
        return json.load(f)

def generate_brief_report(data: dict) -> str:
    """Generate brief mode report text for Telegram"""
    today = datetime.now().strftime("%Y-%m-%d")

    # Extract data
    fred = data["fetched"]["fred"]
    commodities = data["fetched"]["commodities"]
    calc = data["calculated"]
    divergences = data.get("divergences", [])

    # Determine regime
    spx_chg = calc["spx_change"]["value_pct"]
    dgs10_chg = calc["dgs10_change_bp"]["value_bp"]
    wti_chg = calc["wti_change"]["value_pct"]

    if spx_chg < -1 and dgs10_chg > 5 and wti_chg > 2:
        regime = "🔴 Stagflation"
        regime_note = "股债双杀+油价上涨"
    elif spx_chg > 0.5 and dgs10_chg < -5:
        regime = "🟢 Goldilocks"
        regime_note = "股涨债涨"
    elif dgs10_chg > 5:
        regime = "🟡 Reflation 边缘"
        regime_note = "利率上行主导"
    else:
        regime = "⚪ 等待催化剂"
        regime_note = "方向不明"

    # Build report
    report = f"""📊 *每日宏观策略* | {regime}
*日期*: {today}

━━━━━━━━━━━━━━━━━━━━

🎯 *今日核心矛盾*

*利率与风险资产的博弈*

• 10Y: {fred['DGS10']['current']}% ({'+' if dgs10_chg >= 0 else ''}{dgs10_chg:.0f}bp)
• 2Y: {fred['DGS2']['current']}% ({'+' if calc['curve_shape']['chg_2y_bp'] >= 0 else ''}{calc['curve_shape']['chg_2y_bp']:.0f}bp)
• 曲线: {calc['curve_shape']['shape']}
• SPX: {fred['SP500']['current']:.0f} ({spx_chg:+.2f}%)
• VIX: {fred['VIXCLS']['current']:.2f}
• WTI: ${commodities['wti']['current']:.2f}/bbl ({wti_chg:+.2f}%)
• 黄金: ${commodities['gold']['current']:.0f}/oz ({calc['gold_change']['value_pct']:+.2f}%)

━━━━━━━━━━━━━━━━━━━━

📋 *今日关注*

1️⃣ *10Y {4.25 if fred['DGS10']['current'] < 4.25 else 4.50}%关口*
突破→成长股压力; 回落→反弹窗口

2️⃣ *WTI $90支撑*
跌破→利好股市; 反弹$95→滞胀担忧

3️⃣ *SPX {int(fred['SP500']['current'] // 100) * 100}支撑*
跌破→技术破位; 守住→超跌反弹

━━━━━━━━━━━━━━━━━━━━

⚠️ *风险提示*

{regime_note}
定价: 部分定价 | 应对: 保持灵活"""

    # Add divergence if any
    if divergences:
        div = divergences[0]
        report += f"\n\n🔍 *背离*: {div['name']} — {div['description']}"

    report += f"""

━━━━━━━━━━━━━━━━━━━━
_数据: FRED/TwelveData [部分滞后]_
_免责: 仅供参考，不构成投资建议_"""

    return report

def main():
    log("Starting daily macro push...")

    # Fetch data
    data = fetch_data()
    if not data:
        send_telegram("⚠️ 每日宏观报告生成失败：数据获取错误")
        return 1

    log("Data fetched successfully")

    # Generate report
    report = generate_brief_report(data)
    log(f"Report generated ({len(report)} chars)")

    # Send to Telegram
    if send_telegram(report):
        log("Report sent to Telegram successfully")
        return 0
    else:
        log("Failed to send report to Telegram")
        return 1

if __name__ == "__main__":
    sys.exit(main())
