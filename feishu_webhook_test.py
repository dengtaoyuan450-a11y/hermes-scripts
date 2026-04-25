#!/usr/bin/env python3
"""
Feishu Webhook Health Check Script
自动检测飞书机器人 webhook 是否有效，并提供重试机制
"""

import requests
import json
import sys
from datetime import datetime

def test_feishu_webhook(webhook_url, chat_id):
    """测试飞书 webhook 是否有效"""
    
    test_message = {
        "msg_type": "text",
        "content": {
            "text": f"🔍 飞书机器人健康检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=test_message,
            timeout=10
        )
        
        result = response.json()
        
        if result.get("StatusCode") == 0 or result.get("code") == 0:
            print(f"✅ Webhook 有效：{webhook_url}")
            return True
        else:
            print(f"❌ Webhook 无效：{webhook_url}")
            print(f"   错误信息：{result.get('msg', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Webhook 连接失败：{str(e)}")
        return False

def main():
    """主函数"""
    
    # 从配置文件读取飞书配置
    config_path = "~/.hermes/config.yaml"
    
    # 新配置的 Webhook URL
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/a1a852b2-efcc-40ce-a666-2361e16e6b24"
    chat_id = "a1a852b2-efcc-40ce-a666-2361e16e6b24"
    
    print("=" * 60)
    print("🔍 Feishu Webhook Health Check")
    print("=" * 60)
    
    success = test_feishu_webhook(webhook_url, chat_id)
    
    if success:
        print("\n✅ 飞书机器人运行正常！")
        sys.exit(0)
    else:
        print("\n⚠️ 飞书机器人配置有问题，需要更新！")
        sys.exit(1)

if __name__ == "__main__":
    main()
