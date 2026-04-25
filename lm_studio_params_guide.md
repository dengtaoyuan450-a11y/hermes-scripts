# 🔧 LM Studio 模型参数调整完整指南

## 📊 当前状态诊断

### 内存占用分析
```bash
PID      RSS          CPU%     说明
38217    16585MB      62.1%    ⚠️ 模型推理进程（过高）
30624    499MB        4.0%     LM Studio 主进程
812      340MB        0.6%     LM Studio GUI 进程
```

**问题**: 模型占用 **16.5GB 内存**，导致频繁崩溃和连接超时。

---

## 🎯 推荐参数配置表

| 参数项 | 当前值（推测） | **推荐设置** | 作用 | 预期效果 |
|--------|---------------|-------------|------|---------|
| **GPU Layers** | 36-40 (过高) | **30-35** | 控制多少层模型加载到 GPU | 减少显存占用 10-20% |
| **Context Length** | 8192-32768 (过高) | **4096** 或 **8192** | 最大上下文窗口大小 | 减少内存峰值，提升速度 |
| **Batch Size** | 1024-2048 (过高) | **512** | 批处理大小 | 降低内存峰值 |
| **Flash Attention** | ❌ 未启用 | ✅ **启用** | 使用 FlashAttention-2 优化 | 降低内存 30%，提升速度 2x |
| **Max Tokens** | 8192 (过高) | **2048-4096** | 单次生成最大 token 数 | 防止内存溢出 |
| **Rope Scaling** | N/A | **动态** (如果支持) | 旋转位置编码缩放 | 提升长文本处理能力 |

---

## 📝 手动调整步骤（GUI 操作）

### Step 1: 打开 LM Studio
```bash
# macOS
open -a "LM Studio"

# 或使用 Spotlight (Cmd+Space) 搜索 "LM Studio"
```

### Step 2: 切换到 Server 页面
1. 点击左侧边栏的 **🔌 Server** 图标（或按 `Cmd+5`）
2. 确保你的模型 **mlx-community/qwen3.5-35b-a3b** 已加载

### Step 3: 调整推理参数

在 Server 页面中找到以下设置项并修改：

#### 📌 GPU Layers (GPU 层数)
```
┌─────────────────────────────────────┐
│ GPU Layers: [36] → 改为 [32]        │
└─────────────────────────────────────┘

说明: 
- 35B 模型建议设置 30-35 层到 GPU
- 每减少 1 层，显存占用约降低 500MB
```

#### 📌 Context Length (上下文长度)
```
┌─────────────────────────────────────┐
│ Context Length: [16384] → 改为 [4096]│
└─────────────────────────────────────┘

说明:
- 4096 足够处理大多数对话场景
- 如需更长上下文，可设为 8192
```

#### 📌 Batch Size (批处理大小)
```
┌─────────────────────────────────────┐
│ Batch Size: [1024] → 改为 [512]     │
└─────────────────────────────────────┘

说明: 降低批处理大小可减少内存峰值
```

#### 📌 Flash Attention (启用)
```
┌─────────────────────────────────────┐
│ ☑️ Enable Flash Attention           │
└─────────────────────────────────────┘

说明: 
- 如果支持，务必启用
- 可降低内存使用 30%，提升推理速度 2x
```

#### 📌 Max Tokens (最大生成长度)
```
┌─────────────────────────────────────┐
│ Max Tokens: [8192] → 改为 [4096]    │
└─────────────────────────────────────┘

说明: 防止生成过长导致内存溢出
```

### Step 4: 应用设置并重新加载模型
1. 点击 **"Apply"** 或 **"Reload Model"** 按钮
2. 等待模型重新加载完成（约 30-60 秒）
3. 观察内存占用是否下降到 **10-12GB**

---

## ✅ 验证效果

### 运行检查脚本
```bash
~/.hermes/scripts/check_lm_studio.sh
```

### 预期结果对比

| 指标 | 调整前 | **调整后** |
|------|--------|-----------|
| 内存占用 | 16.5GB | **10-12GB** ✅ |
| API 响应时间 | ~430ms | **<350ms** ✅ |
| 崩溃频率 | 频繁 | **显著降低** ✅ |

### 测试命令
```bash
# 快速响应测试
curl -s --max-time 30 http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/qwen3.5-35b-a3b","messages":[{"role":"user","content":"Hello, test response"}],"max_tokens":50}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ OK' if 'choices' in d else '❌ FAIL')"

# 长时间对话测试（模拟实际使用）
for i in {1..5}; do
  echo "测试 $i..."
  curl -s --max-time 60 http://127.0.0.1:1234/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"mlx-community/qwen3.5-35b-a3b","messages":[{"role":"user","content":"Test $i - 这是一个测试消息"}],"max_tokens":100}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ OK' if 'choices' in d else '❌ FAIL')"
  sleep 3
done
```

---

## 🚨 如果问题仍然存在

### 方案 A: 切换到更轻量级模型

推荐替代模型（内存占用更低）：

| 模型 | 参数量 | 内存需求 | 质量评分 |
|------|--------|---------|---------|
| **Qwen2.5-7B-Instruct** | 7B | ~6GB | ⭐⭐⭐⭐ |
| **Llama-3.1-8B-Instruct** | 8B | ~6GB | ⭐⭐⭐⭐⭐ |
| **Gemma-2-9B-it** | 9B | ~7GB | ⭐⭐⭐⭐ |
| **Qwen2.5-14B-Instruct** | 14B | ~10GB | ⭐⭐⭐⭐⭐ |

### 方案 B: 使用量化版本模型

下载 **Q4_K_M** 或 **Q5_K_M** 量化版本：
- Q4: 减少约 40% 内存占用，质量损失 <5%
- Q5: 减少约 25% 内存占用，质量损失 <2%

### 方案 C: 系统级优化

```bash
# 1. 关闭其他占用内存的应用程序
# 2. 确保至少有 16GB 可用系统内存
# 3. 考虑升级到 32GB+ 内存

# 检查系统内存
vm_stat | grep -E "(free|active|inactive)"
```

---

## 📋 快速参考命令

```bash
# 检查 LM Studio 状态
~/.hermes/scripts/check_lm_studio.sh

# 重启 LM Studio（应用新参数）
killall "LM Studio" && open -a "LM Studio"

# 测试 API 响应
curl -s --max-time 30 http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/qwen3.5-35b-a3b","messages":[{"role":"user","content":"Test"}],"max_tokens":20}'

# 查看内存占用
ps aux | grep -i "lm studio" | grep -v grep | awk '{print $2, int($6/1024)"MB", $3"%"}'
```

---

## 📞 需要帮助？

如果调整后问题仍然存在，请提供以下信息：
1. LM Studio 版本（设置 → About）
2. 系统内存总量（`sysctl hw.memsize | awk '{print $1/1024/1024/1024"GB"}'`）
3. 调整后的内存占用截图

---

*最后更新时间：2026-04-13*
