#!/bin/bash
# hermes-scripts 自动同步脚本
# 每小时将本地改动推送到 GitHub

SCRIPTS_DIR="$HOME/.hermes/scripts"
cd "$SCRIPTS_DIR" || exit 1

# 检查是否有改动
if git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "$(date): 无改动，跳过推送"
    exit 0
fi

# 添加所有改动
git add -A

# 检查是否有内容更新
if git diff-index --cached --quiet HEAD -- 2>/dev/null; then
    echo "$(date): 无内容变更"
    exit 0
fi

# 提交
git commit -m "sync: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null

# 推送
git push origin main 2>&1
echo "$(date): 已推送更新到 GitHub"
