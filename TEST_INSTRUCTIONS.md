# 快速测试指令

## ✅ 已修复导入问题

问题原因：`services` 模块需要从项目根目录导入，同时 `model` 模块需要从 `gitSource` 导入。

## 🚀 启动服务

### 方式 1: 使用简化脚本（推荐）

```bash
cd /data/ws/kronos/services
./start_cpu_simple.sh
```

### 方式 2: 手动启动

```bash
cd /data/ws/kronos

export PYTHONPATH="/data/ws/kronos/gitSource:/data/ws/kronos"
export KRONOS_DEVICE=cpu
export KRONOS_SECURITY_ENABLED=false
export KRONOS_RATE_LIMIT_ENABLED=false

python -m uvicorn services.kronos_fastapi.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info
```

### 方式 3: 一行命令

```bash
cd /data/ws/kronos && PYTHONPATH="/data/ws/kronos/gitSource:/data/ws/kronos" KRONOS_DEVICE=cpu KRONOS_SECURITY_ENABLED=false KRONOS_RATE_LIMIT_ENABLED=false python -m uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

## ✅ 验证服务

**新终端窗口** - 等待模型加载（1-2分钟）：

```bash
# 健康检查
curl http://localhost:8000/v1/healthz

# 就绪检查（等待 model_loaded: true）
watch -n 2 'curl -s http://localhost:8000/v1/readyz | python -m json.tool'
```

看到这个表示成功：
```json
{
  "status": "ok",
  "model_loaded": true,
  "device": "cpu",
  "device_warning": null
}
```

## 🧪 运行测试客户端

```bash
cd /data/ws/kronos/services
python test_cpu_prediction.py
```

## 🔍 故障排查

### 如果仍然出现 ModuleNotFoundError

**检查 PYTHONPATH**：
```bash
echo $PYTHONPATH
# 应该包含: /data/ws/kronos/gitSource 和 /data/ws/kronos
```

**手动测试导入**：
```bash
cd /data/ws/kronos
export PYTHONPATH="/data/ws/kronos/gitSource:/data/ws/kronos"
python -c "from model import resolve_device; print('✓ OK')"
python -c "from services.kronos_fastapi.config import get_settings; print('✓ OK')"
```

### 如果端口被占用

```bash
# 查看占用
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或使用其他端口
./start_cpu_simple.sh 8080
```

### 如果模型加载失败

**使用 Hugging Face 自动下载**：
```bash
export KRONOS_MODEL_ID=NeoQuasar/Kronos-small
export KRONOS_TOKENIZER_ID=NeoQuasar/Kronos-Tokenizer-base
unset KRONOS_MODEL_PATH
```

## 📊 预期测试输出

```
======================================================================
⏱️  预测时间统计
======================================================================
总耗时: 12.34 秒
平均每个预测点: 1.234 秒
吞吐量: 0.81 点/秒

预测结果（前3个点）:
  1. 时间: 2024-01-01T11:10:00
     OHLC: O=104.23, H=105.12, L=103.89, C=104.56
```

## 🎯 完整测试流程

### 终端 1 - 启动服务
```bash
cd /data/ws/kronos/services
./start_cpu_simple.sh
```

### 终端 2 - 监控就绪状态
```bash
watch -n 2 'curl -s http://localhost:8000/v1/readyz | python -m json.tool'
```

### 终端 3 - 运行测试（当模型加载完成后）
```bash
cd /data/ws/kronos/services
python test_cpu_prediction.py
```

## ✨ 成功标志

- ✅ 服务启动无错误
- ✅ `/v1/healthz` 返回 `{"status":"ok"}`
- ✅ `/v1/readyz` 返回 `"model_loaded": true, "device": "cpu"`
- ✅ 测试客户端显示预测时间统计
- ✅ 预测结果包含 OHLC 数据

---

**提示**: 如果还有问题，请检查：
1. 当前工作目录是否正确（`pwd` 应该显示 `/data/ws/kronos` 或其子目录）
2. PYTHONPATH 是否正确设置
3. Python 虚拟环境是否激活（如果使用）
