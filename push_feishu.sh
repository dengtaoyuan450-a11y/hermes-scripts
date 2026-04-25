#!/bin/bash

# 盘后布局报告飞书推送脚本
# 读取 stock/2026-MM-DD/目录下的所有缠论报告，生成汇总并推送到飞书

WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/a1a852b2-efcc-40ce-a666-2361e16e6b24"
REPORT_DIR="stock/$(date +%Y-%m-%d)"

# 检查报告目录是否存在
if [ ! -d "$REPORT_DIR" ]; then
    echo "报告目录不存在：$REPORT_DIR"
    exit 1
fi

# 生成汇总报告
SUMMARY="【A 股盘后次日布局】$(date +%Y 年%m 月%d 日) - 缠论分析报告汇总

📊 今日盘后分析标的：
$(ls $REPORT_DIR/*.md 2>/dev/null | xargs -I {} basename {} .md | sed 's/_缠论分析.md//g' | while read code; do
    echo "- $code"
done)

================================================================================
📈 详细分析报告：

$(for report in $REPORT_DIR/*_缠论分析.md; do
    if [ -f "$report" ]; then
        stock_name=$(basename $report | sed 's/_缠论分析.md//g')
        echo "【$stock_name】"
        grep -A 5 "核心结论" $report | head -6
        echo ""
    fi
done)

================================================================================
📋 总体策略总结：

1. 所有标的处于高位震荡区间，建议采取高抛低吸策略
2. 严格设置止损，防止中枢震荡后出现单边突破行情
3. 不建议在当前位置盲目加仓，等待明确买卖信号后再行动

================================================================================
🔔 推送时间：$(date +%Y-%m-%d %H:%M)
"""

# 推送到飞书 webhook
curl -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"$SUMMARY\"}}"

echo ""
echo "✅ 报告已推送到飞书"
