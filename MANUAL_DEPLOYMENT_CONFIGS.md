# Kronos 服务启动方式和配置关系说明书

**文档目的：** 梳理所有启动方式、配置文件关系、优先级顺序

---

## 配置加载机制

Kronos FastAPI 服务使用 **Pydantic Settings**，配置优先级（从高到低）：

```
1. 环境变量（Environment Variables）      ← 最高优先级
2. .env 文件（.env file）
3. 代码默认值（Code defaults in config.py） ← 最低优先级
```

**关键配置文件：**
- `services/kronos_fastapi/config.py` - 配置类定义和默认值
- `services/kronos_fastapi/.env` - 环境变量文件（可选）

---

## 启动方式分类

### 类型 A：手动直接启动（Manual Direct）

不使用任何脚本，直接运行 uvicorn 命令。

#### A1. 最简启动（使用所有默认值）

```bash
cd /data/ws/kronos
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

**配置来源：**
- `config.py` 中的所有默认值
- 如果存在 `.env` 文件，会加载它
- **设备：** `cpu`（默认）
- **模型路径：** `/data/ws/kronos/models`（默认）
- **安全：** 已启用（默认）
- **限流：** 已启用（默认）

#### A2. 指定端口启动

```bash
cd /data/ws/kronos
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 28888
```

**配置来源：**
- 同 A1，仅端口不同
- uvicorn 的 `--port` 参数只影响服务监听端口，不影响应用配置

#### A3. 带环境变量启动（CPU 模式）

```bash
cd /data/ws/kronos
export KRONOS_DEVICE=cpu
export KRONOS_SECURITY_ENABLED=false
export KRONOS_RATE_LIMIT_ENABLED=false
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

**配置来源：**
1. 环境变量覆盖：`KRONOS_DEVICE=cpu`，`KRONOS_SECURITY_ENABLED=false`，`KRONOS_RATE_LIMIT_ENABLED=false`
2. 其他配置：从 `.env`（如果存在）或 `config.py` 默认值

#### A4. 带环境变量启动（GPU 模式）

```bash
cd /data/ws/kronos
export KRONOS_DEVICE=cuda:0
export KRONOS_INFERENCE_TIMEOUT=60
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 8000
```

**配置来源：**
1. 环境变量覆盖：`KRONOS_DEVICE=cuda:0`，`KRONOS_INFERENCE_TIMEOUT=60`
2. 其他配置：从 `.env` 或 `config.py` 默认值

---

### 类型 B：脚本启动（Shell Script）

使用现有的便捷脚本启动。

#### B1. `./start_cpu_simple.sh` （你之前使用的）

**位置：** `/data/ws/kronos/services/start_cpu_simple.sh`

**配置来源：**
1. **脚本设置的环境变量**（最高优先级）：
   ```bash
   KRONOS_DEVICE=cpu
   KRONOS_LOG_LEVEL=INFO
   KRONOS_SECURITY_ENABLED=false
   KRONOS_RATE_LIMIT_ENABLED=false
   KRONOS_INFERENCE_TIMEOUT=240
   KRONOS_REQUEST_TIMEOUT=300
   ```
2. `.env` 文件（如果存在）- **但会被脚本的环境变量覆盖**
3. `config.py` 默认值

**使用方法：**
```bash
cd /data/ws/kronos/services
./start_cpu_simple.sh          # 默认端口 8000
./start_cpu_simple.sh 28888    # 自定义端口 28888
```

**特点：**
- ✅ CPU 模式
- ✅ 安全功能禁用（开发模式）
- ✅ 限流禁用
- ✅ 超时时间较长（适合 CPU）
- ✅ 简单快速启动

#### B2. `./start_cpu_simple_v2.sh` （增强版）

**位置：** `/data/ws/kronos/services/start_cpu_simple_v2.sh`

**配置来源：** 同 B1，但增加了：
```bash
KRONOS_STARTUP_TIMEOUT=300  # 额外的启动超时配置
```

**使用方法：**
```bash
cd /data/ws/kronos/services
./start_cpu_simple_v2.sh          # 默认端口 8000
./start_cpu_simple_v2.sh 28888    # 自定义端口 28888
```

#### B3. `./start_gpu_simple.sh`

**位置：** `/data/ws/kronos/services/start_gpu_simple.sh`

**配置来源：**
1. **脚本设置的环境变量**：
   ```bash
   KRONOS_DEVICE=cuda:0            # GPU 模式
   KRONOS_LOG_LEVEL=INFO
   KRONOS_SECURITY_ENABLED=false
   KRONOS_RATE_LIMIT_ENABLED=false
   KRONOS_INFERENCE_TIMEOUT=60     # GPU 推理快，超时短
   KRONOS_REQUEST_TIMEOUT=90
   ```
2. `.env` 文件（如果存在）
3. `config.py` 默认值

**使用方法：**
```bash
cd /data/ws/kronos/services
./start_gpu_simple.sh          # 默认端口 8000
./start_gpu_simple.sh 28888    # 自定义端口 28888
```

**特点：**
- ✅ GPU 模式（cuda:0）
- ✅ 检查 GPU 可用性
- ✅ 较短超时（GPU 推理快）

#### B4. `services/kronos_fastapi/start.sh` （旧版通用脚本）

**位置：** `/data/ws/kronos/services/kronos_fastapi/start.sh`

**配置来源：**
- 不设置环境变量
- 完全依赖 `.env` 文件和 `config.py` 默认值

**使用方法：**
```bash
cd /data/ws/kronos/gitSource
../services/kronos_fastapi/start.sh          # 默认端口 8000，开发模式
../services/kronos_fastapi/start.sh 28888    # 自定义端口
../services/kronos_fastapi/start.sh 8000 0.0.0.0 4  # 生产模式，4 workers
```

---

### 类型 C：Docker 部署（Container）

#### C1. CPU 专用配置

**配置文件：** `services/kronos_fastapi/docker-compose.cpu.yml`

**配置来源：**
- Docker Compose 文件中的 `environment` 部分
- 主要配置：
  ```yaml
  KRONOS_DEVICE=cpu
  KRONOS_RATE_LIMIT_PER_MINUTE=100
  KRONOS_MAX_REQUEST_SIZE_MB=10
  ```

**使用方法：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
docker-compose -f docker-compose.cpu.yml up -d
# 或使用脚本
./deploy-cpu.sh
```

#### C2. GPU 专用配置

**配置文件：** `services/kronos_fastapi/docker-compose.gpu.yml`

**配置来源：**
- Docker Compose 文件中的 `environment` 部分
- GPU 运行时配置
- 主要配置：
  ```yaml
  KRONOS_DEVICE=cuda:0
  NVIDIA_VISIBLE_DEVICES=0
  KRONOS_RATE_LIMIT_PER_MINUTE=200  # GPU 更高限流
  KRONOS_MAX_REQUEST_SIZE_MB=20     # GPU 更大请求
  ```

**使用方法：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
docker-compose -f docker-compose.gpu.yml up -d
# 或使用脚本
./deploy-gpu.sh
```

#### C3. 混合部署（CPU + GPU）

**配置文件：** `services/kronos_fastapi/docker-compose.hybrid.yml`

**配置来源：**
- 同时定义两个服务：`kronos-api-cpu` 和 `kronos-api-gpu`
- 每个服务有独立的环境配置
- NGINX 负载均衡器配置：`nginx.conf`

**使用方法：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
# 不带负载均衡器
docker-compose -f docker-compose.hybrid.yml up -d

# 带负载均衡器
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer up -d

# 或使用脚本
./deploy-hybrid.sh --with-lb
```

---

## 配置优先级实例

### 实例 1：`./start_cpu_simple.sh` + 存在 `.env` 文件

假设 `.env` 文件包含：
```bash
KRONOS_DEVICE=cuda:0              # GPU 配置
KRONOS_SECURITY_ENABLED=true      # 安全启用
KRONOS_INFERENCE_TIMEOUT=60
```

运行 `./start_cpu_simple.sh` 后，实际配置：
```bash
KRONOS_DEVICE=cpu                 # 被脚本覆盖 ✓
KRONOS_SECURITY_ENABLED=false     # 被脚本覆盖 ✓
KRONOS_INFERENCE_TIMEOUT=240      # 被脚本覆盖 ✓
KRONOS_REQUEST_TIMEOUT=300        # 被脚本设置 ✓
```

**结论：** 脚本中的 `export` 优先级最高，覆盖 `.env` 文件。

### 实例 2：手动 `uvicorn` + `.env` 文件

假设 `.env` 文件包含：
```bash
KRONOS_DEVICE=cpu
KRONOS_SECURITY_ENABLED=false
```

运行：
```bash
cd /data/ws/kronos
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 28888
```

实际配置：
```bash
KRONOS_DEVICE=cpu                 # 从 .env 读取 ✓
KRONOS_SECURITY_ENABLED=false     # 从 .env 读取 ✓
KRONOS_RATE_LIMIT_ENABLED=true    # config.py 默认值 ✓
KRONOS_INFERENCE_TIMEOUT=240      # config.py 默认值 ✓
```

**结论：** `.env` 文件覆盖 `config.py` 默认值。

### 实例 3：手动 `uvicorn` + 环境变量 + `.env` 文件

假设 `.env` 文件包含：
```bash
KRONOS_DEVICE=cpu
KRONOS_SECURITY_ENABLED=false
```

运行：
```bash
cd /data/ws/kronos
export KRONOS_DEVICE=cuda:0           # 手动设置环境变量
export KRONOS_INFERENCE_TIMEOUT=30
uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 28888
```

实际配置：
```bash
KRONOS_DEVICE=cuda:0              # 环境变量优先 ✓
KRONOS_SECURITY_ENABLED=false     # .env 文件 ✓
KRONOS_INFERENCE_TIMEOUT=30       # 环境变量优先 ✓
```

**结论：** 环境变量 > `.env` 文件 > `config.py` 默认值。

---

## 配置完整对照表

| 启动方式 | 设备 | 安全 | 限流 | 推理超时 | 配置来源 |
|---------|------|------|------|---------|---------|
| **手动 uvicorn**（无环境变量） | cpu | true | true | 240s | `.env` 或 `config.py` |
| **手动 uvicorn**（有环境变量） | 环境变量 | 环境变量 | 环境变量 | 环境变量 | 环境变量优先 |
| **start_cpu_simple.sh** | cpu | false | false | 240s | 脚本环境变量 |
| **start_cpu_simple_v2.sh** | cpu | false | false | 240s | 脚本环境变量 |
| **start_gpu_simple.sh** | cuda:0 | false | false | 60s | 脚本环境变量 |
| **docker-compose.cpu.yml** | cpu | true | true | 240s | Docker env |
| **docker-compose.gpu.yml** | cuda:0 | true | true | 240s | Docker env |
| **docker-compose.hybrid.yml** | 两者 | true | true | 240s | Docker env |

---

## 常见问题

### Q1: 我用 `./start_cpu_simple.sh`，为什么设备是 CPU？

**答：** 脚本中明确设置了 `export KRONOS_DEVICE=cpu`，这会覆盖所有其他配置（包括 `.env` 文件）。

### Q2: 手动运行 `uvicorn services.kronos_fastapi.main:app --host 0.0.0.0 --port 28888` 使用的是哪个配置？

**答：**
1. 如果你之前 `export` 了环境变量，使用环境变量
2. 否则，如果存在 `.env` 文件，使用 `.env` 配置
3. 否则，使用 `config.py` 中的默认值

**当前 `.env` 配置：**
```bash
KRONOS_DEVICE=cpu
KRONOS_SECURITY_ENABLED=false
KRONOS_RATE_LIMIT_ENABLED=false
KRONOS_INFERENCE_TIMEOUT=240
```

所以实际使用的是 **CPU 模式 + 无安全限制 + 240s 超时**。

### Q3: 如何确认当前使用的配置？

**方法 1：** 检查服务 `/v1/readyz` 端点
```bash
curl http://localhost:8000/v1/readyz | jq .
```

返回示例：
```json
{
  "status": "ready",
  "model_loaded": true,
  "device": "cpu"  // 或 "cuda:0"
}
```

**方法 2：** 查看日志（启动时打印配置）
```bash
# 手动启动时查看终端输出
# Docker 启动时查看日志
docker logs kronos-api-cpu
```

### Q4: 我想用 GPU，应该用哪个启动方式？

**开发/测试：**
```bash
cd /data/ws/kronos/services
./start_gpu_simple.sh 28888
```

**生产环境：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-gpu.sh
# 或
docker-compose -f docker-compose.gpu.yml up -d
```

### Q5: `.env` 文件会被脚本覆盖吗？

**不会。** 脚本只在运行时设置环境变量，不会修改 `.env` 文件本身。但脚本的环境变量会**覆盖** `.env` 文件的配置。

---

## 推荐使用方式

### 开发环境

**CPU 开发：**
```bash
cd /data/ws/kronos/services
./start_cpu_simple.sh 8000
```

**GPU 开发：**
```bash
cd /data/ws/kronos/services
./start_gpu_simple.sh 8000
```

**优点：**
- 快速启动
- 无需 Docker
- 安全功能禁用（方便调试）
- 限流禁用

### 生产环境

**CPU 生产：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-cpu.sh
```

**GPU 生产：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-gpu.sh
```

**混合部署（推荐）：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-hybrid.sh --with-lb
```

**优点：**
- Docker 隔离
- 自动重启
- 健康检查
- 资源限制
- 安全功能启用

---

## 配置文件位置速查

| 文件路径 | 用途 |
|---------|------|
| `services/kronos_fastapi/config.py` | 配置类定义和默认值 |
| `services/kronos_fastapi/.env` | 环境变量配置文件 |
| `services/start_cpu_simple.sh` | CPU 快速启动脚本 |
| `services/start_gpu_simple.sh` | GPU 快速启动脚本 |
| `services/kronos_fastapi/docker-compose.cpu.yml` | CPU Docker 配置 |
| `services/kronos_fastapi/docker-compose.gpu.yml` | GPU Docker 配置 |
| `services/kronos_fastapi/docker-compose.hybrid.yml` | 混合 Docker 配置 |
| `services/kronos_fastapi/deploy-cpu.sh` | CPU 部署脚本 |
| `services/kronos_fastapi/deploy-gpu.sh` | GPU 部署脚本 |
| `services/kronos_fastapi/deploy-hybrid.sh` | 混合部署脚本 |

---

## 总结

**配置优先级：**
```
环境变量（export/脚本） > .env 文件 > config.py 默认值
```

**你之前使用的 `./start_cpu_simple.sh`：**
- ✅ 使用脚本设置的环境变量（最高优先级）
- ✅ CPU 模式，无安全限制，240s 超时
- ✅ 适合开发测试

**手动 `uvicorn` 命令：**
- ✅ 使用当前 shell 的环境变量（如果有）
- ✅ 否则使用 `.env` 文件
- ✅ 否则使用 `config.py` 默认值

**推荐：**
- 开发：使用 `start_cpu_simple.sh` 或 `start_gpu_simple.sh`
- 生产：使用 Docker 部署（`deploy-*.sh` 脚本）
