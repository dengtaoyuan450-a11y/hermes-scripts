#!/bin/bash

# LM Studio 模型参数调整指南脚本
# 此脚本提供手动操作步骤，因为 LM Studio 的 GUI 设置无法通过 API 直接修改

echo "=========================================="
echo "🔧 LM Studio 模型参数调整指南"
echo "=========================================="
echo ""

# 检查 LM Studio 是否运行
if ! pgrep -f "LM Studio" > /dev/null; then
    echo "❌ LM Studio 未运行！请先启动 LM Studio。"
    exit 1
fi

echo "✅ LM Studio 正在运行"
echo ""

# 显示当前内存占用
echo "📊 当前 LM Studio 进程状态:"
ps aux | grep -i "lm studio" | grep -v grep | awk 'BEGIN {printf "%-8s %-12s %-8s %s\n", "PID", "RSS", "CPU%", "进程"}' | head -1
ps aux | grep -i "lm studio" | grep -v grep | awk '{printf "%-8s %-12s %-8s %s\n", $2, int($6/1024)"MB", $3"%", $11}'
echo ""

# 提供调整步骤
cat << 'EOF'
==========================================
📝 手动调整 LM Studio 参数的步骤：
==========================================

1️⃣ 打开 LM Studio GUI
   - 在应用程序列表中查找 "LM Studio" 并打开
   - 或使用 Spotlight (Cmd+Space) 搜索 "LM Studio"

2️⃣ 切换到模型服务器页面
   - 点击左侧边栏的 🔌 "Server" 图标（或按 Cmd+5）
   - 确保你的模型 "mlx-community/qwen3.5-35b-a3b" 已加载

3️⃣ 调整推理参数（关键步骤）
   ┌─────────────────────────────────────────┐
   │ 在 Server 页面中找到以下设置：          │
   └─────────────────────────────────────────┘

   📌 GPU Layers (GPU 层数):
      - 当前值：可能是 36-40（过高）
      - 推荐设置：**30-35**
      - 作用：减少 GPU 显存占用
   
   📌 Context Length (上下文长度):
      - 当前值：可能是 8192-32768（过高）
      - 推荐设置：**4096** 或 **8192**
      - 作用：减少内存占用，提升响应速度
   
   📌 Batch Size (批处理大小):
      - 当前值：可能是 1024-2048（过高）
      - 推荐设置：**512**
      - 作用：减少内存峰值
   
   📌 Flash Attention:
      - 推荐：**✅ 启用** (如果支持)
      - 作用：显著降低内存使用，提升速度
   
   📌 Max Tokens (最大生成长度):
      - 推荐设置：**2048** 或 **4096**
      - 作用：防止生成过长导致内存溢出

4️⃣ 应用设置
   - 点击 "Apply" 或 "Reload Model" 按钮
   - 等待模型重新加载完成

5️⃣ 验证效果
   - 观察内存占用是否下降到 **10-12GB** 左右
   - API 响应时间应该更快（<500ms）

==========================================
💡 额外优化建议：
==========================================

🔹 如果内存仍然不足，考虑：
   - 切换到更轻量级的模型（如 Qwen2.5-7B-Instruct）
   - 使用量化版本模型（Q4_K_M 或 Q5_K_M）

🔹 系统级优化：
   - 关闭其他占用内存的应用程序
   - 确保至少有 16GB 可用系统内存

🔹 监控脚本：
   - 运行以下命令检查状态：
     ~/.hermes/scripts/check_lm_studio.sh

==========================================
🚀 快速重启 LM Studio（如果参数调整后）：
==========================================

# 在终端执行以下命令重启 LM Studio：
killall "LM Studio" && open -a "LM Studio"

echo ""
echo "✅ 请按照上述步骤手动调整 LM Studio 参数。"
echo "完成后，运行以下命令验证效果："
echo "  ~/.hermes/scripts/check_lm_studio.sh"
