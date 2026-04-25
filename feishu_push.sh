#!/bin/bash
# feishu_push.sh - 飞书推送脚本
# 用于将选股报告推送到飞书机器人

# 加载 .env 文件（如果存在）
ENV_FILE="$HOME/.hermes/.env"
if [ -f "$ENV_FILE" ]; then
    # 读取 .env 文件中的变量并导出到当前环境
    while IFS='=' read -r key value; do
        # 跳过注释和空行
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        
        # 导出变量（去除引号）
        value=$(echo "$value" | sed 's/^"//;s/"$//')
        export "$key=$value"
    done < "$ENV_FILE"
fi

# 从环境变量获取飞书 webhook URL
FEISHU_WEBHOOK="${FEISHU_WEBHOOK_URL:-}"

if [ -z "$FEISHU_WEBHOOK" ]; then
    echo "⚠️ 飞书 Webhook URL 未配置，跳过推送"
    exit 0
fi

# 从标准输入读取报告内容
REPORT=$(cat)

if [ -z "$REPORT" ]; then
    echo "⚠️ 报告内容为空，跳过推送"
    exit 0
fi

# 构建飞书消息体
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Build JSON payload safely using python3 to avoid shell escaping issues
PAYLOAD=$(echo "$REPORT" | python3 -c "
import sys, json

timestamp = '$TIMESTAMP'
report = sys.stdin.read()

# Feishu markdown content should be a single string with \n for line breaks
clean_report = report.strip()

payload = {
    'msg_type': 'interactive',
    'card': {
        'header': {
            'title': {
                'tag': 'plain_text',
                'content': f'A 股选股报告 - {timestamp}'
            },
            'template': 'red'
        },
        'elements': [
            {
                'tag': 'markdown',
                'content': clean_report
            }
        ]
    }
}

print(json.dumps(payload, ensure_ascii=False))
")

curl -s -X POST "$FEISHU_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

echo ""
echo "✅ 飞书推送完成"
