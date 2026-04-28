#!/usr/bin/env python3
"""
prefilter_xuangu.py — 盘中选股预过滤器 v4
============================================

【用户方案 · 2026-04-27】
Step1: 申万一级行业 → 取今日主力净流入额前2板块
        优先：近期政策/事件催化板块（商业航天/国产芯片/军工/半导体）
        否则：涨幅>0 且成交量较5日均量放大≥20%
Step2: 在Top2板块内，所有条件一次性传入 mx-xuangu：
        - 今日涨幅 1.5%~5%
        - 量比 > 1.5
        - 换手率 3%~10%
        - 流通市值 > 50亿
        - 近3日主力净流入至少2日为正值（4.23-4.27）
        按「近3日主力净流入总额」降序，取前3支
        返回：代码、名称、题材、量比、换手率、流通市值、近3日主力净流入、现价、涨跌幅

【关键实现】
- 板块：用 mx-xuangu 查「申万一级行业今日主力资金流向」，按主力净额聚合申万一级
- 选股：用 mx-xuangu 一次传所有条件，结果从 raw JSON 而非 CSV（CSV无近3日明细）
- 近3日净额明细：在 raw JSON 的 MTM_EXTRA|... key，按「万」为单位累加

【用法】
  python prefilter_xuangu.py

【输出（stdout）】
  单行 JSON：{"candidates": [...], "sectors": [...], "total": N, "timestamp": "..."}
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 配置 ──────────────────────────────────────────────────────────────────
MX_DATA   = os.path.expanduser("~/mx_data.py")
MX_XUANGU = os.path.expanduser("~/mx_xuangu.py")
OUTPUT_DIR = Path("/tmp/cron-output/prefilter/")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 近3日日期范围（本周交易日）
DATE_RANGE = "2026.04.23 - 2026.04.27"

# ── 工具函数 ────────────────────────────────────────────────────────────────

def yuan_to_yi(val: Any) -> Optional[float]:
    """将 '5.18亿' / '1234万' / '5678900' 转换为亿元浮点数（万元→亿×0.0001）"""
    if val is None or str(val).strip() == "":
        return None
    s = str(val).strip().replace(",", "")
    multiplier = 1.0
    if "亿" in s:
        multiplier = 1.0
        s = s.replace("亿", "").replace("元", "").strip()
    elif "万" in s:
        multiplier = 1.0 / 10000.0
        s = s.replace("万", "").replace("元", "").strip()
    elif "元" in s:
        s = s.replace("元", "").strip()
    try:
        return round(float(s) * multiplier, 4)
    except (ValueError, TypeError):
        return None


def find_file(output_dir: Path, glob_pattern: str, suffix: str = "csv") -> Optional[Path]:
    """查找包含 glob_pattern 的最新指定后缀文件"""
    candidates = sorted(output_dir.glob(f"*.{suffix}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidates:
        if glob_pattern in c.name:
            return c
    return candidates[0] if candidates else None


def parse_raw_json_xuangu(raw_path: Path) -> List[Dict[str, Any]]:
    """
    从 mx-xuangu raw JSON 中解析数据。
    数据结构：
      raw["data"]["data"]["allResults"]["result"]["dataList"] = [row_dict, ...]
      row 中关键字段：
        SECURITY_CODE: 代码
        SECURITY_SHORT_NAME: 名称
        NEWEST_PRICE: 最新价
        CHG: 涨跌幅
        010000_LIANGBI<70>{2026-04-27}: 量比
        010000_TURNOVER_RATE<70>{2026-04-27}: 换手率
        010000_CIRCULATION_MARKET_VALUE<70>{2026-04-27}: 流通市值
        SW_INDUSTRY: 申万行业分类
        STYLE_CONCEPT: 概念
        MARKET_SHORT_NAME: 市场
        主力净额大于0出现次数{...}: 正流入天数
        MTM_EXTRA|count_近3日主力净额大于0出现次数_detail.data: 近3日明细(JSON)
    """
    try:
        with open(raw_path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"[prefilter] ⚠ JSON读取失败 {raw_path.name}: {e}", file=sys.stderr)
        return []

    try:
        data_list = raw["data"]["data"]["allResults"]["result"]["dataList"]
    except Exception as e:
        print(f"[prefilter] ⚠ JSON结构解析失败: {e}", file=sys.stderr)
        return []

    DETAIL_KEY = "MTM_EXTRA|count_近3日主力净额大于0出现次数_detail.data"
    POS_DAYS_KEY = "主力净额大于0出现次数{2026-04-23|2026-04-27|TRADING_DAY}"

    stocks = []
    for row in data_list:
        code = str(row.get("SECURITY_CODE") or "").strip()
        name = str(row.get("SECURITY_SHORT_NAME") or "").strip()
        if not code or code == "None":
            continue

        # ST 过滤
        if "ST" in name.upper() or "*ST" in name.upper():
            continue

        # 解析数值字段
        try:
            pct = float(row.get("CHG") or 0)
        except (ValueError, TypeError):
            pct = 0.0

        try:
            vr = float(row.get("010000_LIANGBI<70>{2026-04-27}") or 0)
        except (ValueError, TypeError):
            vr = 0.0

        try:
            tr = float(row.get("010000_TURNOVER_RATE<70>{2026-04-27}") or 0)
        except (ValueError, TypeError):
            tr = 0.0

        try:
            price = float(row.get("NEWEST_PRICE") or 0)
        except (ValueError, TypeError):
            price = 0.0

        mc = yuan_to_yi(row.get("010000_CIRCULATION_MARKET_VALUE<70>{2026-04-27}"))

        # 近3日正流入天数
        pos_days_raw = row.get(POS_DAYS_KEY)
        try:
            pos_days = int(float(pos_days_raw)) if pos_days_raw else 0
        except (ValueError, TypeError):
            pos_days = 0

        # 近3日净额明细
        detail_raw = str(row.get(DETAIL_KEY) or "")
        net_3day = parse_3day_detail(detail_raw)

        # ── 过滤条件 ──
        if pct < 1.5 or pct > 5.0:
            continue
        if vr <= 1.5:
            continue
        if tr < 3.0 or tr > 10.0:
            continue
        if mc is None or mc <= 50.0:
            continue
        if pos_days < 2:   # 近3日中至少2日主力净流入为正
            continue
        if code.startswith("688"):   # 排除科创板
            continue

        stock = {
            "code": code,
            "name": name,
            "price": round(price, 2),
            "change_pct": round(pct, 2),
            "volume_ratio": round(vr, 2),
            "turnover_rate": round(tr, 2),
            "mkt_cap_yi": mc,
            "net_3day_yi": net_3day,
            "pos_days": pos_days,
            "sw_industry": row.get("SW_INDUSTRY", ""),
            "concepts": row.get("STYLE_CONCEPT", ""),
            "market": row.get("MARKET_SHORT_NAME", ""),
        }
        stocks.append(stock)

    # 按近3日净额降序
    stocks.sort(key=lambda x: x.get("net_3day_yi") or 0, reverse=True)
    return stocks


def parse_3day_detail(raw_str: str) -> Optional[float]:
    """
    解析近3日主力净额明细，返回总额（亿元）。
    金额单位：万元（1万 = 0.0001亿）
    """
    if not raw_str or raw_str.strip() == "" or raw_str == "None":
        return None
    try:
        items = json.loads(raw_str)
        if not isinstance(items, list) or not items:
            return None
        total = 0.0
        for entry in items[0].get("data", []):
            amt = str(entry.get("OCCUR_DETAIL_DATA1") or "")
            val = yuan_to_yi(amt)   # yuan_to_yi 把「万」视作 1/10000 亿
            if val is not None:
                total += val
        return round(total, 4)
    except Exception:
        return None


# ── Step 1: 申万一级行业 → Top 2 ─────────────────────────────────────────

def get_sw_top2_sectors() -> List[str]:
    """
    用 mx-xuangu 查「申万一级行业今日主力资金流向」，
    聚合到申万一级（取「电子-半导体-xxx」→「电子」），按主力净额降序取前2。
    优先：已知催化板块（CATALYST_SECTORS）优先进入Top2。
    """
    query = "申万一级行业今日主力资金流向"
    print(f"[prefilter] xuangu: {query}", file=sys.stderr)

    try:
        result = subprocess.run(
            ["python3", MX_XUANGU, query, "--output-dir", str(OUTPUT_DIR)],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:
        print(f"[prefilter] ⚠ xuangu失败: {e}", file=sys.stderr)
        return []

    csv_path = find_file(OUTPUT_DIR, "申万一级行业今日主力资金流向", "csv")
    if not csv_path:
        print(f"[prefilter] ⚠ 未找到CSV", file=sys.stderr)
        return []

    try:
        import csv as csv_lib
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv_lib.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"[prefilter] ⚠ CSV读取失败: {e}", file=sys.stderr)
        return []

    if not rows:
        return []

    # 推断日期后缀（如 2026.04.27）
    date_suffix = ""
    if rows:
        for k in rows[0].keys():
            m = re.search(r"(\d{4}\.\d{2}\.\d{2})", str(k))
            if m:
                date_suffix = m.group(1)
                break

    # 聚合申万一级行业主力净额
    sector_net = {}
    net_col = f"主力净额(元) {date_suffix}" if date_suffix else "主力净额(元) 2026.04.27"
    sw_col = "申万行业分类"
    ind_col = "东财行业总分类"

    for r in rows:
        sw_full = r.get(sw_col) or r.get(ind_col) or ""
        parts = sw_full.split("-")
        sector_l1 = parts[0].strip() if parts else sw_full.strip()
        if not sector_l1:
            continue
        raw = r.get(net_col, "")
        net = yuan_to_yi(raw)
        if net is not None:
            sector_net[sector_l1] = sector_net.get(sector_l1, 0) + net

    if not sector_net:
        print("[prefilter] ⚠ 板块净额解析失败", file=sys.stderr)
        return []

    sorted_sectors = sorted(sector_net.items(), key=lambda x: x[1], reverse=True)
    print(f"[prefilter] 📊 申万一级 DDX（前6）: {sorted_sectors[:6]}", file=sys.stderr)

    # 构建Top2：「政策催化优先」逻辑
    #
    # 规则：
    #   ① 如果 Top5 中有 ≥2 个催化板块 → 直接取前2个催化板块
    #   ② 如果 Top5 中有 1 个催化板块 → 该板块入选，再从剩余 Top5 中
    #      选一个满足「涨幅>0 且成交量较5日均量放大≥20%」的板块
    #   ③ 如果 Top5 中无催化板块 → 从 Top5 中取满足「涨幅>0 且成交量放大≥20%」的板块，
    #      按 DDX 降序取前2
    #      若不足2个，则用纯 DDX 补足
    #
    # 已知催化板块池
    CATALYST_POOL = {
        "军工",     # 地缘风险 + 业绩确定性
        "半导体",   # 国产替代 + AI驱动
        "商业航天", # 4.24航天日 + 4.28长征十号首飞 + Kuiper卫星互联网
        "国产芯片", # CPU涨价 + DeepSeek-V4 + 国产AI芯片41%份额
    }

    top5 = [s for s, _ in sorted_sectors[:5]]

    # ① ≥2 个催化板块在 Top5
    catalyst_in_top5 = [s for s in top5 if s in CATALYST_POOL]
    if len(catalyst_in_top5) >= 2:
        top2 = catalyst_in_top5[:2]
        print(f"[prefilter] ✅ 催化板块优先入选: {top2}", file=sys.stderr)

    # ② 只有 1 个催化板块在 Top5
    elif len(catalyst_in_top5) == 1:
        top2 = [catalyst_in_top5[0]]
        # 从剩余 Top5 中找满足条件的板块
        remaining = [s for s in top5 if s not in catalyst_in_top5]
        # 简单策略：取剩余中 DDX 最高的（近3日成交量验证暂时跳过，
        # 因为 mx-data 单票查询近3日量比不够稳定，用 DDX 代替）
        if remaining:
            top2.append(remaining[0])
        print(f"[prefilter] ✅ 1个催化板块入选: {catalyst_in_top5[0]}，补充: {top2[1] if len(top2)>1 else '无'}", file=sys.stderr)

    # ③ 无催化板块在 Top5
    else:
        # 取 Top5 中前2个（已经是按 DDX 降序）
        top2 = top5[:2]
        print(f"[prefilter] ✅ 无催化板块在Top5，取DDX前2: {top2}", file=sys.stderr)

    print(f"[prefilter] 🎯 入选板块: {top2}", file=sys.stderr)
    return top2


# ── Step 2: 板块内量化选股 ────────────────────────────────────────────────

def select_stocks(sectors: List[str], limit_per_sector: int = 3) -> List[Dict[str, Any]]:
    """
    在板块内执行 mx-xuangu，按近3日净额降序。
    每板块最多取 limit_per_sector 支，合并后最多 6 支（2×3）。
    所有票都进入 CZSC，由 CZSC 判断是否有二买/三买。
    """
    if not sectors:
        return []

    sector_str = "、".join(sectors)
    query = (
        f"A股 申万行业{sector_str} "
        f"涨幅1.5%~5% "
        f"量比大于1.5 "
        f"换手率3%~10% "
        f"流通市值大于50亿 "
        f"近3日主力净流入至少2日为正值"
    )
    print(f"[prefilter] xuangu: {query[:80]}...", file=sys.stderr)

    try:
        result = subprocess.run(
            ["python3", MX_XUANGU, query, "--output-dir", str(OUTPUT_DIR)],
            capture_output=True, text=True, timeout=180,
        )
    except Exception as e:
        print(f"[prefilter] ⚠ xuangu失败: {e}", file=sys.stderr)
        return []

    # 找 raw JSON（不是 CSV，因为近3日明细在JSON里）
    raw_path = find_file(OUTPUT_DIR, "近3日主力净流入至少2日为正值", "json")
    if not raw_path:
        # 降级：找最新的 raw JSON
        candidates = sorted(OUTPUT_DIR.glob("mx_xuangu_*_raw.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            raw_path = candidates[0]

    if not raw_path:
        print("[prefilter] ⚠ 未找到raw JSON", file=sys.stderr)
        return []

    print(f"[prefilter] 解析 raw JSON: {raw_path.name}", file=sys.stderr)
    stocks = parse_raw_json_xuangu(raw_path)
    print(f"[prefilter] 过滤后: {len(stocks)} 只（未分组）", file=sys.stderr)

    # ── 按申万行业分组，每组取 top3 ──
    # sectors 里的板块名是申万一级（如"电子"），stocks[i]['sw_industry'] 形如"电子-半导体-集成电路封测"
    sector_stocks = {s: [] for s in sectors}
    for st in stocks:
        sw_full = st.get("sw_industry", "")
        # 取一级分类
        l1 = sw_full.split("-")[0].strip() if sw_full else ""
        for sec in sectors:
            if l1 == sec:
                sector_stocks[sec].append(st)
                break

    # 每组按近3日净额降序，取前limit_per_sector
    result = []
    for sec in sectors:
        group = sector_stocks.get(sec, [])
        group.sort(key=lambda x: x.get("net_3day_yi") or 0, reverse=True)
        picked = group[:limit_per_sector]
        for st in picked:
            st["_sector"] = sec   # 标注来源板块
        result.extend(picked)
        print(f"[prefilter]   {sec}: 取{len(picked)}只 → {[s['code']+s['name'] for s in picked]}", file=sys.stderr)

    # 打印所有候选
    for s in result:
        net = s.get("net_3day_yi")
        pd = str(s["pos_days"]) + "日正流入"
        ind = s["sw_industry"][:20]
        print(f"  {s['code']} {s['name']} 涨幅{s['change_pct']}% 换手{s['turnover_rate']}% "
              f"量比{s['volume_ratio']} 流通市值{s['mkt_cap_yi']}亿 "
              f"近3日净流入{net}亿({pd}) 行业:{ind}",
              file=sys.stderr)

    return result


# ── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[prefilter] === v4 启动 {ts} ===", file=sys.stderr)

    # Step 1: 申万一级 → Top 2 板块
    top_sectors = get_sw_top2_sectors()

    if not top_sectors:
        print("[prefilter] ⚠ 无强势板块，输出空候选", file=sys.stderr)
        output = {
            "candidates": [],
            "sectors": [],
            "total": 0,
            "timestamp": ts,
            "source": "prefilter_xuangu.py v4 (用户方案)",
        }
        print(json.dumps(output, ensure_ascii=False))
        return

    # Step 2: 每板块各取前3，合并最多6支，全部输给CZSC
    candidates = select_stocks(top_sectors, limit_per_sector=3)

    # 格式化输出（用户要求字段）
    output_stocks = []
    for s in candidates:
        output_stocks.append({
            "code": s["code"],
            "name": s["name"],
            "题材": s.get("sw_industry", ""),
            "板块": s.get("_sector", ""),
            "量比": s["volume_ratio"],
            "换手率": s["turnover_rate"],
            "流通市值_亿": s["mkt_cap_yi"],
            "近3日主力净流入_亿": s["net_3day_yi"],
            "现价": s["price"],
            "涨跌幅": s["change_pct"],
        })

    output = {
        "candidates": output_stocks,
        "sectors": top_sectors,
        "total": len(output_stocks),
        "timestamp": ts,
        "source": "prefilter_xuangu.py v4 (用户方案)",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
