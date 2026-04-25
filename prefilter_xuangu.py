#!/usr/bin/env python3
"""
prefilter_xuangu.py — 盘中起爆选股预过滤器
============================================

用作 cron job 的 script 参数：在 agent 启动前自动运行，
执行 mx-xuangu 选股并输出紧凑 JSON 到 stdout（注入到 prompt 首行）。

【角色定位】
- 数据收集层 — 运行 mx-xuangu 查询，收集原始选股结果
- 数据清洗层 — 去除冗余字段，统一单位（亿）
- 数据压缩层 — 将 200+KB 原始 JSON 压缩至 <2KB 紧凑 JSON

【用法】
  python prefilter_xuangu.py

【输出（stdout）】
  单行 JSON：
  {"candidates": [...], "total": N, "timestamp": "..."}

【上游依赖】
  - ~/mx_xuangu.py（symlink 到 skills/mx-xuangu/mx_xuangu.py）
  - MX_APIKEY 环境变量
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# ── 配置 ────────────────────────────────────────────────────────────────
MX_XUANGU = os.path.expanduser("~/mx_xuangu.py")

# 与 Job 3 Step2 一致的选股查询
QUERIES = [
    "开盘30分钟涨幅2-5% 主力净流入为正 非ST 流通市值50-500亿",
    "早盘主力净流入前20 涨幅小于5% 流通市值50-500亿 技术形态突破",
]

OUTPUT_DIR = Path("/tmp/cron-output/prefilter/")

# 需要从 CSV 提取的核心字段（中文名（无日期后缀） → 英文 key）
ESSENTIAL_FIELDS = {
    "代码": "code",
    "名称": "name",
    "市场代码简称": "market",
    "最新价(元)": "price",
    "涨跌幅(%)": "change_pct",
    "主力净额(元)": "net_inflow",
    "换手率(%)": "turnover_rate",
    "量比": "volume_ratio",
    "流通市值(元)": "market_cap",
}

# ── 工具函数 ────────────────────────────────────────────────────────────


def safe_filename(s: str, max_len: int = 80) -> str:
    """将查询文本转为安全文件名"""
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    return s.strip().replace(" ", "_")[:max_len]


def parse_value(val: str) -> Any:
    """尝试将字符串转为数字"""
    if val == "" or val is None:
        return None
    val = val.strip().replace(",", "")
    try:
        if "." in val:
            return float(val)
        return int(val)
    except (ValueError, TypeError):
        return val


def map_csv_column(col_name: str, cn_key: str) -> bool:
    """检查CSV列名是否匹配中文key（支持日期后缀模糊）"""
    if col_name == cn_key:
        return True
    # 支持 "最新价(元) 2026.04.24" → "最新价(元)"
    if col_name.startswith(cn_key) and col_name[len(cn_key):].startswith(" "):
        return True
    return False


def build_column_map(csv_columns: List[str]) -> Dict[str, str]:
    """建立 CSV列名 → 英文key 的映射"""
    mapping = {}
    for csv_col in csv_columns:
        for cn_key, en_key in ESSENTIAL_FIELDS.items():
            if map_csv_column(csv_col, cn_key):
                mapping[csv_col] = en_key
                break
    return mapping


def yuan_to_yi(val: Any) -> Optional[float]:
    """将元转换为亿元"""
    if val is None or str(val).strip() == "":
        return None
    v = parse_value(str(val))
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v) / 100_000_000, 2)
    return None


# ── CSV 读取（带列名映射） ──────────────────────────────────────────────


def read_csv_with_mapping(path: Path) -> List[Dict[str, Any]]:
    """读取 UTF-8 BOM CSV 并将中文列名映射为英文 key"""
    rows = []
    try:
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return []
            col_map = build_column_map(reader.fieldnames)
            print(f"[prefilter] 列名映射: {col_map}", file=sys.stderr)
            for row in reader:
                mapped = {}
                for csv_col, val in row.items():
                    en_key = col_map.get(csv_col)
                    if en_key:
                        mapped[en_key] = val
                if mapped.get("code"):  # 至少要有 code 才算有效行
                    rows.append(mapped)
    except Exception as e:
        print(f"[prefilter] ⚠ 读取 CSV 失败 {path}: {e}", file=sys.stderr)
    return rows


def find_csv_file(output_dir: Path, query: str) -> Optional[Path]:
    """查找 mx-xuangu 生成的 CSV 文件路径"""
    safe_name = safe_filename(query)
    exact = output_dir / f"mx_xuangu_{safe_name}.csv"
    if exact.exists():
        return exact
    # 回退：扫描最近文件
    candidates = sorted(output_dir.glob("mx_xuangu_*.csv"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]
    return None


# ── 股票数据处理 ────────────────────────────────────────────────────────


def stock_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """从 CSV 行字典（英文 key）解析为标准股票对象"""
    stock = {}
    # code — 保持原始字符，去空格
    raw_code = row.get("code", "")
    stock["code"] = str(raw_code).strip() if raw_code else None
    # name
    stock["name"] = row.get("name") or None
    # market (SH/SZ)
    stock["market"] = row.get("market") or None
    # price — 浮点数，2位小数
    p = parse_value(str(row.get("price", "")))
    stock["price"] = round(float(p), 2) if isinstance(p, (int, float)) else None
    # change_pct
    c = parse_value(str(row.get("change_pct", "")))
    stock["change_pct"] = round(float(c), 2) if isinstance(c, (int, float)) else None
    # net_inflow — 元→亿
    stock["net_inflow"] = yuan_to_yi(row.get("net_inflow"))
    # turnover_rate
    t = parse_value(str(row.get("turnover_rate", "")))
    stock["turnover_rate"] = round(float(t), 2) if isinstance(t, (int, float)) else None
    # volume_ratio
    v = parse_value(str(row.get("volume_ratio", "")))
    stock["volume_ratio"] = round(float(v), 2) if isinstance(v, (int, float)) else None
    # market_cap — 元→亿
    stock["market_cap"] = yuan_to_yi(row.get("market_cap"))
    return stock


def merge_dedup(stocks_list: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """合并多组选股结果，按 code 去重（保留第一条）"""
    seen = set()
    merged = []
    for batch in stocks_list:
        for s in batch:
            code = s.get("code")
            if code and code not in seen:
                seen.add(code)
                merged.append(s)
    return merged


# ── 主流程 ──────────────────────────────────────────────────────────────


def run_xuangu_query(query: str, output_dir: Path) -> List[Dict[str, Any]]:
    """执行一条 mx-xuangu 查询并返回解析后的股票列表"""
    print(f"[prefilter] 执行选股: {query}", file=sys.stderr)

    try:
        result = subprocess.run(
            ["python3", MX_XUANGU, query, "--output-dir", str(output_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print(f"[prefilter] ⚠ 超时: {query[:40]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[prefilter] ⚠ 执行失败: {e}", file=sys.stderr)
        return []

    if result.returncode != 0:
        print(f"[prefilter] ⚠ 返回码 {result.returncode}: {result.stderr[:200]}",
              file=sys.stderr)
        return []

    csv_path = find_csv_file(output_dir, query)
    if not csv_path:
        print(f"[prefilter] ⚠ 未找到 CSV: {query[:40]}", file=sys.stderr)
        return []

    raw_rows = read_csv_with_mapping(csv_path)
    stocks = [stock_from_row(r) for r in raw_rows if r.get("code")]
    print(f"[prefilter] ✅ {query[:30]}... → {len(stocks)} 只", file=sys.stderr)
    return stocks


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_batches = []
    total_raw = 0

    for query in QUERIES:
        stocks = run_xuangu_query(query, OUTPUT_DIR)
        if stocks:
            all_batches.append(stocks)
            total_raw += len(stocks)

    merged = merge_dedup(all_batches)

    print(f"[prefilter] 📊 原始总计: {total_raw} → 去重后: {len(merged)} 只",
          file=sys.stderr)

    output = {
        "candidates": merged,
        "total": len(merged),
        "total_raw": total_raw,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "prefilter_xuangu.py",
    }

    # stdout → 注入到 cron prompt
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
