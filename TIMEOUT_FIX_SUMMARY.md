# 超时问题修复总结

## 🐛 问题

测试 400→120 配置时出现：
```
✗ HTTP 504 错误
响应内容: {"detail":"Prediction timeout after 30 seconds"}
```

## 🔍 根本原因

服务使用了 `config.py` 中的**硬编码默认值 30 秒**：

```python
# config.py 第 45 行
inference_timeout: int = Field(30, env="KRONOS_INFERENCE_TIMEOUT")
                              ^^^ 默认 30 秒！
```

虽然：
- `.env` 文件设置了 `KRONOS_INFERENCE_TIMEOUT=120`
- 启动脚本设置了 `export KRONOS_INFERENCE_TIMEOUT=120`

但 **120 秒对于 400→120 长序列预测仍然不够**！

## ✅ 已修复

### 1. 更新 .env 文件
```bash
# 从 120 秒增加到 240 秒
KRONOS_INFERENCE_TIMEOUT=240  # 4 分钟
KRONOS_REQUEST_TIMEOUT=300    # 5 分钟
```

### 2. 更新启动脚本
```bash
# start_cpu_simple.sh
export KRONOS_INFERENCE_TIMEOUT=240
export KRONOS_REQUEST_TIMEOUT=300
```

### 3. 创建新启动脚本
```bash
# start_cpu_simple_v2.sh - 增强版，显式显示超时配置
```

## 🚀 重启服务

**步骤**:

1. **停止当前服务**  
   在运行服务的终端按 `Ctrl+C`

2. **启动服务**（选择一种方式）

   方式 A - 使用原脚本（已更新）:
   ```bash
   cd /data/ws/kronos/services
   ./start_cpu_simple.sh
   ```

   方式 B - 使用新脚本（推荐，显示更多信息）:
   ```bash
   cd /data/ws/kronos/services
   ./start_cpu_simple_v2.sh
   ```

3. **验证配置**  
   启动时应该看到：
   ```
   推理超时: 240秒
   请求超时: 300秒
   ```

4. **等待模型加载**（1-2 分钟）

5. **重新运行测试**
   ```bash
   cd /data/ws/kronos/services
   python test_cpu_prediction_400.py
   ```

## 📊 超时配置对比

### 修复前
```
代码默认:  30 秒  ← 太短！
启动脚本: 120 秒  ← 仍不够
.env文件: 120 秒  ← 仍不够
客户端:   300 秒  ← 正常
```

### 修复后
```
代码默认:  30 秒（被覆盖）
启动脚本: 240 秒  ← ✓ 足够
.env文件: 240 秒  ← ✓ 足够
客户端:   300 秒  ← ✓ 足够
```

## 🎯 预期结果

修复后，400→120 测试应该：
- **不会超时** ✓
- **完成时间**: 25-30 秒
- **显示性能统计**: 吞吐量约 4-5 点/秒
- **与原始 example 对比**: 性能相当

## 🔧 如果还是超时

如果 240 秒仍然不够（不太可能），继续增加：

```bash
# 编辑启动脚本
nano /data/ws/kronos/services/start_cpu_simple.sh

# 修改为 10 分钟
export KRONOS_INFERENCE_TIMEOUT=600
export KRONOS_REQUEST_TIMEOUT=720
```

## 💡 经验教训

1. **Pydantic 的 Field 默认值会被使用**，即使环境变量存在
2. **环境变量必须在服务启动时设置**，修改 .env 不够
3. **超时层级必须正确**: `客户端 > 请求 > 推理`
4. **长序列需要更长超时**: 不是线性关系

## 📝 相关文件

- 配置文件: `services/kronos_fastapi/.env`
- 启动脚本: `services/start_cpu_simple.sh`
- 增强脚本: `services/start_cpu_simple_v2.sh`
- 测试脚本: `services/test_cpu_prediction_400.py`
- 超时文档: `services/TIMEOUT_CONFIGURATION.md`
