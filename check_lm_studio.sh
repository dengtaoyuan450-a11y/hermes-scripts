#!/bin/bash
# LM Studio 健康检查脚本
# 用于在 cron 任务执行前验证本地模型服务是否可用

set -e

echo "Checking LM Studio health status..."

# Check if port is listening
if nc -z localhost 1234 2>/dev/null; then
    echo "LM Studio service is running (port 1234)"
    
    # Try to get model list to verify response
    if curl -s --max-time 5 http://localhost:1234/v1/models > /dev/null 2>&1; then
        echo "LM Studio API response is normal"
        exit 0
    else
        echo "LM Studio API response timeout"
        exit 1
    fi
else
    echo "LM Studio service is not running!"
    echo "Please start LM Studio or check http://127.0.0.1:1234"
    exit 1
fi
