# Kronos 超时配置说明

## 📋 超时层级

Kronos 系统有**三层超时设置**，从内到外：

```
客户端超时 (test_cpu_prediction_400.py)
    ↓
FastAPI 请求超时 (uvicorn/FastAPI)
    ↓
模型推理超时 (predictor.py)
```

## 🔧 超时配置详解

### 1. 客户端超时（最外层）

**位置**: `test_cpu_prediction_400.py` 第 178 行

```python
response = self.session.post(
    f"{self.base_url}/v1/predict/single",
    json=request_data,
    timeout=300  # 5分钟超时 ← 可以调整
)
```

**当前设置**: 300 秒 (5 分钟)

**作用**: 客户端等待服务器响应的最长时间

**何时触发**: 
- 服务器处理时间超过 300 秒
- 网络故障导致无响应

**建议值**:
- 短序列 (100→10): `timeout=60` (1 分钟)
- 长序列 (400→120): `timeout=300` (5 分钟)
- 超长序列或多采样: `timeout=600` (10 分钟)

### 2. FastAPI 请求超时（中间层）

**位置**: `services/kronos_fastapi/.env.cpu`

```bash
# 请求总超时（包括所有处理时间）
KRONOS_REQUEST_TIMEOUT=180  # 3 分钟
```

**当前设置**: 180 秒 (3 分钟)

**作用**: FastAPI 处理单个请求的最长时间

**何时触发**:
- 单次预测请求处理时间超过 180 秒
- 包括数据验证、推理、序列化等所有步骤

**建议值**:
- CPU 短序列: `KRONOS_REQUEST_TIMEOUT=120` (2 分钟)
- CPU 长序列: `KRONOS_REQUEST_TIMEOUT=300` (5 分钟)
- GPU 模式: `KRONOS_REQUEST_TIMEOUT=60` (1 分钟)

⚠️ **注意**: 需要 < 客户端超时，否则客户端先超时

### 3. 模型推理超时（最内层）

**位置**: `services/kronos_fastapi/.env.cpu`

```bash
# 模型推理超时（纯推理时间）
KRONOS_INFERENCE_TIMEOUT=120  # 2 分钟
```

**当前设置**: 120 秒 (2 分钟)

**作用**: 单次 `predictor.predict()` 调用的最长时间

**何时触发**:
- 纯模型推理时间超过 120 秒
- 不包括数据准备和结果序列化

**建议值**:
- CPU 短序列: `KRONOS_INFERENCE_TIMEOUT=60` (1 分钟)
- CPU 长序列: `KRONOS_INFERENCE_TIMEOUT=180` (3 分钟)
- GPU 模式: `KRONOS_INFERENCE_TIMEOUT=30` (30 秒)

⚠️ **注意**: 需要 < 请求超时，否则请求先超时

### 4. 启动超时

**位置**: `services/kronos_fastapi/.env.cpu`

```bash
# 服务启动超时（模型加载时间）
KRONOS_STARTUP_TIMEOUT=300  # 5 分钟
```

**作用**: 模型加载的最长等待时间

## 📊 当前配置总览

### 默认配置 (.env.cpu)

| 超时类型 | 当前值 | 适用场景 |
|---------|--------|---------|
| 客户端超时 | 300秒 | 400→120 长序列 |
| 请求超时 | 180秒 | FastAPI 总处理时间 |
| 推理超时 | 120秒 | 模型推理时间 |
| 启动超时 | 300秒 | 模型加载 |

### 超时关系

```
客户端超时 (300秒)
  > 请求超时 (180秒)
    > 推理超时 (120秒)
```

⚠️ **问题**: 当前配置下，400→120 可能超时！

原因：
- 预估推理时间：25-30 秒
- 推理超时：120 秒 ✓
- 请求超时：180 秒 ✓
- 客户端超时：300 秒 ✓

**应该没问题，但如果超时，继续往下看调整方案。**

## 🔧 针对 400→120 的推荐配置

### 方案 1: 保守配置（推荐）

**编辑** `.env` 文件：

```bash
# 推理超时 - 增加到 4 分钟
KRONOS_INFERENCE_TIMEOUT=240

# 请求超时 - 增加到 5 分钟
KRONOS_REQUEST_TIMEOUT=300
```

**客户端**（`test_cpu_prediction_400.py`）：
```python
timeout=360  # 6 分钟
```

### 方案 2: 激进配置（更长时间）

**编辑** `.env` 文件：

```bash
# 推理超时 - 增加到 10 分钟
KRONOS_INFERENCE_TIMEOUT=600

# 请求超时 - 增加到 12 分钟
KRONOS_REQUEST_TIMEOUT=720
```

**客户端**：
```python
timeout=900  # 15 分钟
```

### 方案 3: 仅调整客户端（最简单）

只修改 `test_cpu_prediction_400.py`：

```python
# 第 178 行
timeout=600  # 改为 10 分钟
```

## 🚀 如何调整超时

### 方法 1: 修改 .env 文件（影响所有请求）

```bash
cd /data/ws/kronos/services/kronos_fastapi

# 备份
cp .env .env.backup

# 编辑
nano .env

# 修改以下行:
KRONOS_INFERENCE_TIMEOUT=240
KRONOS_REQUEST_TIMEOUT=300

# 保存后重启服务
```

### 方法 2: 修改测试脚本（仅影响此测试）

```bash
cd /data/ws/kronos/services

# 编辑
nano test_cpu_prediction_400.py

# 找到第 178 行，修改:
timeout=600  # 改为 10 分钟

# 保存
```

### 方法 3: 环境变量覆盖（临时）

```bash
# 启动服务时设置
cd /data/ws/kronos/services
export KRONOS_INFERENCE_TIMEOUT=300
export KRONOS_REQUEST_TIMEOUT=360
./start_cpu_simple.sh
```

## 🎯 针对不同场景的配置建议

### 场景 1: 快速测试 (100→10)

```bash
# .env
KRONOS_INFERENCE_TIMEOUT=60
KRONOS_REQUEST_TIMEOUT=90

# 客户端
timeout=120
```

### 场景 2: 标准预测 (400→120)

```bash
# .env
KRONOS_INFERENCE_TIMEOUT=180
KRONOS_REQUEST_TIMEOUT=240

# 客户端
timeout=300
```

### 场景 3: 多采样 (400→120, sample_count=5)

```bash
# .env
KRONOS_INFERENCE_TIMEOUT=600
KRONOS_REQUEST_TIMEOUT=720

# 客户端
timeout=900
```

## 📝 快速调整命令

### 增加超时（运行前执行）

```bash
cd /data/ws/kronos/services/kronos_fastapi

# 临时增加超时
sed -i 's/KRONOS_INFERENCE_TIMEOUT=120/KRONOS_INFERENCE_TIMEOUT=300/' .env
sed -i 's/KRONOS_REQUEST_TIMEOUT=180/KRONOS_REQUEST_TIMEOUT=360/' .env

# 查看修改
grep TIMEOUT .env

# 重启服务生效
```

### 恢复默认

```bash
cd /data/ws/kronos/services/kronos_fastapi

# 复制默认配置
cp .env.cpu .env

# 或手动恢复
sed -i 's/KRONOS_INFERENCE_TIMEOUT=.*/KRONOS_INFERENCE_TIMEOUT=120/' .env
sed -i 's/KRONOS_REQUEST_TIMEOUT=.*/KRONOS_REQUEST_TIMEOUT=180/' .env
```

## 🔍 超时故障排查

### 如果看到 "requests.exceptions.Timeout"

**原因**: 客户端超时

**解决**: 增加客户端 `timeout` 值

### 如果看到 "Inference timeout"

**原因**: 模型推理超时

**解决**: 增加 `KRONOS_INFERENCE_TIMEOUT`

### 如果看到 "Request timeout"

**原因**: FastAPI 请求处理超时

**解决**: 增加 `KRONOS_REQUEST_TIMEOUT`

## 💡 最佳实践

1. **层级关系**: 确保 `客户端 > 请求 > 推理`
2. **留余量**: 每层比下层多 20-50%
3. **测试调整**: 先运行一次，根据实际时间调整
4. **CPU vs GPU**: GPU 可以用更短超时
5. **生产环境**: 使用保守值（宁可等待，不要超时）

## 📋 当前推荐

对于 **400→120 测试**，建议：

```bash
# 编辑 .env
KRONOS_INFERENCE_TIMEOUT=240  # 4 分钟（足够 25-30 秒的推理）
KRONOS_REQUEST_TIMEOUT=300    # 5 分钟

# test_cpu_prediction_400.py 保持
timeout=300  # 5 分钟（与请求超时一致）
```

这样配置应该完全足够！
