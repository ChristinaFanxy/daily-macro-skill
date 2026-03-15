#!/usr/bin/env python3
"""
报告数值校验脚本

用法:
    python3 scripts/validate_report.py --report report.md --data data/2026-03-13.json

功能:
    - 从报告 Markdown 中提取数值
    - 与 JSON 数据文件对比
    - 输出校验结果 (PASS/FAIL + 差异列表)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# 需要校验的字段映射: (报告中的标签, JSON路径, 容差, 单位)
VALIDATION_RULES: List[Tuple[str, str, float, str]] = [
    ("美债2Y", "fetched.fred.DGS2.current", 0.01, "%"),
    ("美债10Y", "fetched.fred.DGS10.current", 0.01, "%"),
    ("美债30Y", "fetched.fred.DGS30.current", 0.01, "%"),
    ("实际利率", "fetched.fred.DFII10.current", 0.01, "%"),
    ("VIX", "fetched.fred.VIXCLS.current", 0.1, ""),
    ("DXY", "fetched.fred.DTWEXBGS.current", 0.01, ""),
    ("USD/JPY", "fetched.fred.DEXJPUS.current", 0.01, ""),
    ("S&P 500", "fetched.fred.SP500.current", 1.0, ""),
    ("HY OAS", "fetched.fred.BAMLH0A0HYM2.current", 0.01, "%"),
    ("2s10s利差", "calculated.spread_2s10s.value_bp", 0.5, "bp"),
    ("Breakeven", "calculated.breakeven.value_pct", 0.01, "%"),
    ("铜金比", "calculated.copper_gold_ratio.value", 0.001, ""),
    ("WTI", "fetched.commodities.wti.current", 0.1, "$/bbl"),
    ("黄金", "fetched.commodities.gold.current", 1.0, "$/oz"),
    ("铜", "fetched.commodities.copper.current", 0.01, "$/lb"),
]


def extract_value_from_json(data: Dict[str, Any], path: str) -> Optional[float]:
    """从 JSON 中按路径提取值"""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def extract_values_from_report(report_text: str) -> Dict[str, Optional[float]]:
    """
    从报告 Markdown 中提取数值
    支持多种格式:
    - | 美债2Y | 3.64% |
    - | 美债2Y | 3.64 |
    - 美债2Y: 3.64%
    """
    extracted: Dict[str, Optional[float]] = {}

    for label, _, _, unit in VALIDATION_RULES:
        # 尝试从表格中提取: | 标签 | 数值 |
        # 匹配模式: | 标签 | 数值(可能带单位) |
        pattern = rf"\|\s*{re.escape(label)}\s*\|\s*\$?([\d.,]+)\s*(?:{re.escape(unit)}|%|bp|/\w+)?\s*\|"
        match = re.search(pattern, report_text)

        if match:
            try:
                # 移除逗号并转换为浮点数
                value_str = match.group(1).replace(",", "")
                extracted[label] = float(value_str)
            except ValueError:
                extracted[label] = None
        else:
            # 尝试其他格式: 标签: 数值 或 标签 数值
            pattern2 = rf"{re.escape(label)}[:\s]+\$?([\d.,]+)\s*(?:{re.escape(unit)}|%|bp)?"
            match2 = re.search(pattern2, report_text)
            if match2:
                try:
                    value_str = match2.group(1).replace(",", "")
                    extracted[label] = float(value_str)
                except ValueError:
                    extracted[label] = None
            else:
                extracted[label] = None

    return extracted


def validate_report(report_path: str, data_path: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    校验报告中的数值与 JSON 数据是否一致

    Returns:
        (is_valid, discrepancies)
        - is_valid: True 如果所有数值都在容差范围内
        - discrepancies: 差异列表
    """
    # 读取文件
    report_text = Path(report_path).read_text(encoding="utf-8")
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))

    # 提取报告中的数值
    report_values = extract_values_from_report(report_text)

    discrepancies: List[Dict[str, Any]] = []
    all_valid = True

    for label, json_path, tolerance, unit in VALIDATION_RULES:
        expected = extract_value_from_json(data, json_path)
        actual = report_values.get(label)

        result: Dict[str, Any] = {
            "label": label,
            "json_path": json_path,
            "expected": expected,
            "actual": actual,
            "unit": unit,
            "status": "UNKNOWN",
        }

        if expected is None:
            result["status"] = "SKIP"
            result["reason"] = "JSON 中无此数据"
        elif actual is None:
            result["status"] = "SKIP"
            result["reason"] = "报告中未找到此数值"
        else:
            diff = abs(expected - actual)
            result["diff"] = diff

            if diff <= tolerance:
                result["status"] = "PASS"
            else:
                result["status"] = "FAIL"
                result["reason"] = f"差异 {diff:.4f} 超过容差 {tolerance}"
                all_valid = False

        discrepancies.append(result)

    return all_valid, discrepancies


def print_results(is_valid: bool, discrepancies: List[Dict[str, Any]]) -> None:
    """打印校验结果"""
    print("\n" + "=" * 60)
    print("📊 报告数值校验结果")
    print("=" * 60 + "\n")

    # 分类统计
    passed = [d for d in discrepancies if d["status"] == "PASS"]
    failed = [d for d in discrepancies if d["status"] == "FAIL"]
    skipped = [d for d in discrepancies if d["status"] == "SKIP"]

    # 打印失败项
    if failed:
        print("❌ 校验失败的字段:\n")
        for d in failed:
            print(f"  {d['label']}:")
            print(f"    期望值 (JSON): {d['expected']}{d['unit']}")
            print(f"    实际值 (报告): {d['actual']}{d['unit']}")
            print(f"    差异: {d['diff']:.4f}")
            print(f"    原因: {d['reason']}")
            print()

    # 打印通过项
    if passed:
        print("✅ 校验通过的字段:\n")
        for d in passed:
            print(f"  {d['label']}: {d['actual']}{d['unit']} ✓")
        print()

    # 打印跳过项
    if skipped:
        print("⏭️ 跳过的字段:\n")
        for d in skipped:
            print(f"  {d['label']}: {d['reason']}")
        print()

    # 总结
    print("-" * 60)
    print(f"统计: {len(passed)} 通过 | {len(failed)} 失败 | {len(skipped)} 跳过")
    print("-" * 60)

    if is_valid:
        print("\n🎉 校验结果: PASS - 所有数值与 JSON 一致\n")
    else:
        print("\n⚠️ 校验结果: FAIL - 存在数值不一致\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="校验报告中的数值与 JSON 数据是否一致")
    parser.add_argument("--report", "-r", type=str, required=True, help="报告 Markdown 文件路径")
    parser.add_argument("--data", "-d", type=str, required=True, help="JSON 数据文件路径")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出结果")
    parser.add_argument("--quiet", "-q", action="store_true", help="仅输出 PASS/FAIL")
    args = parser.parse_args(argv)

    # 检查文件存在
    if not Path(args.report).exists():
        print(f"错误: 报告文件不存在: {args.report}", file=sys.stderr)
        return 1
    if not Path(args.data).exists():
        print(f"错误: 数据文件不存在: {args.data}", file=sys.stderr)
        return 1

    # 执行校验
    is_valid, discrepancies = validate_report(args.report, args.data)

    # 输出结果
    if args.json:
        result = {
            "is_valid": is_valid,
            "discrepancies": discrepancies,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.quiet:
        print("PASS" if is_valid else "FAIL")
    else:
        print_results(is_valid, discrepancies)

    return 0 if is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
