#!/usr/bin/env python3
"""
Feishu Push Script - 飞书推送脚本
用于将选股报告推送到飞书机器人

Usage: python3 feishu_push.py [report_content]
       echo "report" | python3 feishu_push.py
"""

import requests
import json
import sys
from datetime import datetime

def push_to_feishu(webhook_url, report_content):
    """推送报告到飞书"""
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 构建飞书消息体（交互式卡片）
    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"A 股选股报告 - {timestamp}"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": report_content
                }
            ]
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=message,
            timeout=30
        )
        
        result = response.json()
        
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            print(f"✅ 飞书推送完成 - {timestamp}")
            return True
        else:
            print(f"❌ 飞书推送失败：{result.get('msg', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ 飞书推送异常：{str(e)}")
        return False

def main():
    """主函数"""
    
    # 从环境变量或命令行参数获取 webhook URL
    import os
    
    # 尝试从 .env 文件读取（与 bash 脚本兼容）
    env_file = os.path.expanduser("~/.hermes/.env")
    webhook_url = None
    
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('FEISHU_WEBHOOK_URL='):
                    webhook_url = line.split('=', 1)[1].strip().strip('"')
                    break
    
    # 如果 .env 中没有，尝试从环境变量获取
    if not webhook_url:
        webhook_url = os.environ.get('FEISHU_WEBHOOK_URL', '')
    
    # 如果还是没有，使用默认值（所有 3 个 job 共用同一个 webhook）
    if not webhook_url:
        webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/a1a852b2-efcc-40ce-a666-2361e16e6b24"
    
    # 从命令行参数或 stdin 读取报告内容
    if len(sys.argv) > 1:
        report_content = sys.argv[1]
    else:
        # 从 stdin 读取（兼容 bash 脚本的用法）
        report_content = sys.stdin.read()
    
    if not report_content.strip():
        print("⚠️ 报告内容为空，跳过推送")
        sys.exit(0)
    
    # 推送报告
    success = push_to_feishu(webhook_url, report_content)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
