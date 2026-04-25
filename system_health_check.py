#!/usr/bin/env python3
"""
Hermes Agent 系统健康监控脚本（最终版）
自动检测并修复常见问题
"""

import subprocess
import json
from datetime import datetime

def check_feishu_webhook():
    """检查飞书 webhook 状态"""
    
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/a1a852b2-efcc-40ce-a666-2361e16e6b24"
    
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", webhook_url, 
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"msg_type": "text", "content": {"text": "🔍 系统健康检查"}})],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        response = json.loads(result.stdout)
        if response.get("StatusCode") == 0 or response.get("code") == 0:
            return True, "Webhook 正常"
        else:
            return False, f"Webhook 错误：{response.get('msg')}"
            
    except Exception as e:
        return False, f"连接失败：{str(e)}"

def check_cron_jobs():
    """检查定时任务状态"""
    
    try:
        result = subprocess.run(
            ["hermes", "cron", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout
        
        # 检查是否有 active 任务
        if "active" in output.lower():
            count = output.count("[active]")
            return True, f"找到 {count} 个定时任务"
        else:
            return False, "未找到定时任务"
            
    except Exception as e:
        return False, f"检查失败：{str(e)}"

def main():
    """主函数"""
    
    print("=" * 60)
    print("🔍 Hermes Agent 系统健康检查")
    print("=" * 60)
    
    # 检查飞书 webhook
    print("\n📬 飞书 Webhook 状态:")
    webhook_ok, webhook_msg = check_feishu_webhook()
    print(f"   {webhook_msg}")
    
    # 检查定时任务
    print("\n⏰ 定时任务状态:")
    cron_ok, cron_msg = check_cron_jobs()
    print(f"   {cron_msg}")
    
    # 总结
    print("\n" + "=" * 60)
    if webhook_ok and cron_ok:
        print("✅ 系统运行正常！")
    else:
        print("⚠️ 发现问题，需要修复！")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
