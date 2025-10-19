# 开发模式启动说明 - 不依赖 .env 文件

**更新日期：** 2025-10-16
**变更原因：** 解决 .env 文件导致的设备配置冲突问题

---

## 问题背景

### 之前的问题

用户使用 `./start_gpu_simple.sh` 启动 GPU 模式时，虽然脚本设置了：
```bash
export KRONOS_DEVICE=cuda:0
```

但服务实际加载的配置仍然是：
```
device=cpu
```

**根本原因：**
- Pydantic Settings 优先读取 `.env` 文件
- `.env` 文件包含 `KRONOS_DEVICE=cpu`
- 导致脚本的环境变量被 `.env` 文件覆盖

---

## 解决方案

### 修改策略

所有开发启动脚本现在会：
1. **自动检测 `.env` 文件**
2. **临时禁用 `.env` 文件**（重命名为 `.env.disabled`）
3. **完全通过脚本的环境变量控制配置**
4. **退出时自动恢复 `.env` 文件**

### 修改的脚本

1. `services/start_cpu_simple.sh`
2. `services/start_cpu_simple_v2.sh`
3. `services/start_gpu_simple.sh`

---

## 工作原理

### 启动时

```bash
./start_gpu_simple.sh
  ↓
1. 检测 .env 文件
  ↓
2. 如果存在：
   - 提示：⚠️  检测到 .env 文件，临时禁用以避免配置冲突
   - 重命名：.env → .env.disabled
  ↓
3. 设置环境变量：
   export KRONOS_DEVICE=cuda:0
   export KRONOS_SECURITY_ENABLED=false
   ...
  ↓
4. 启动服务：
   python -m uvicorn services.kronos_fastapi.main:app ...
  ↓
5. 注册退出清理函数（trap）
```

### 退出时（Ctrl+C 或正常退出）

```bash
Ctrl+C 或 退出
  ↓
触发 trap 清理函数
  ↓
恢复 .env 文件：
  .env.disabled → .env
  ↓
提示：恢复 .env 文件...
```

---

## 使用方法

### CPU 模式开发

```bash
cd /data/ws/kronos/services
./start_cpu_simple.sh [端口]

# 示例
./start_cpu_simple.sh          # 默认端口 8000
./start_cpu_simple.sh 28888    # 自定义端口 28888
```

**配置（完全由脚本控制）：**
- 设备：CPU
- 安全：禁用
- 限流：禁用
- 推理超时：240秒
- 请求超时：300秒

### GPU 模式开发

```bash
cd /data/ws/kronos/services
./start_gpu_simple.sh [端口]

# 示例
./start_gpu_simple.sh          # 默认端口 8000
./start_gpu_simple.sh 28888    # 自定义端口 28888
```

**配置（完全由脚本控制）：**
- 设备：cuda:0
- 安全：禁用
- 限流：禁用
- 推理超时：60秒（GPU 快）
- 请求超时：90秒

---

## 验证配置

### 启动后检查

```bash
# 健康检查
curl http://localhost:8000/v1/healthz

# 就绪检查（包含设备信息）
curl http://localhost:8000/v1/readyz | jq .
```

**预期响应（GPU 模式）：**
```json
{
  "status": "ready",
  "model_loaded": true,
  "device": "cuda:0"  // ✓ 正确
}
```

**预期响应（CPU 模式）：**
```json
{
  "status": "ready",
  "model_loaded": true,
  "device": "cpu"  // ✓ 正确
}
```

### 查看日志确认

启动日志应该显示：
```
{"message": "Service configuration: device=cuda:0, ..."}  // GPU 模式
{"message": "Service configuration: device=cpu, ..."}     // CPU 模式
```

---

## 常见问题

### Q1: .env 文件会被删除吗？

**答：** 不会。脚本只是临时重命名为 `.env.disabled`，退出时会自动恢复。

### Q2: 如果我强制杀掉进程（kill -9），.env 会恢复吗？

**答：** 不会。强制杀掉会跳过清理函数。需要手动恢复：

```bash
cd /data/ws/kronos/services/kronos_fastapi
if [ -f .env.disabled ]; then
    mv .env.disabled .env
fi
```

### Q3: 我可以永久删除 .env 文件吗？

**答：** 可以，但不推荐。.env 文件是为 Docker 部署准备的。开发模式现在会自动处理冲突。

**如果你确定只用脚本启动，可以：**
```bash
cd /data/ws/kronos/services/kronos_fastapi
mv .env .env.backup  # 备份
```

### Q4: Docker 部署还需要 .env 吗？

**答：** 不需要。Docker 部署使用 `docker-compose.*.yml` 中的 `environment` 配置，不依赖 `.env` 文件。

### Q5: 我怎么知道脚本正在使用哪个配置？

**答：** 脚本启动时会打印配置信息：

```
配置:
  端口: 8000
  设备: cuda:0
  推理超时: 60秒
  请求超时: 90秒
```

---

## 配置优先级（修改后）

### 开发模式（脚本启动）

```
脚本环境变量（export）← 最高优先级（唯一来源）
  ↓
.env 文件 ← 已禁用
  ↓
config.py 默认值 ← 仅在脚本未设置时使用
```

**效果：** 配置完全由脚本控制，不受 .env 影响。

### Docker 部署

```
docker-compose.yml 的 environment ← 最高优先级
  ↓
.env 文件 ← 不使用（Docker 忽略）
  ↓
config.py 默认值 ← 最低优先级
```

---

## 测试步骤

### 测试 GPU 模式

```bash
# 1. 启动 GPU 服务
cd /data/ws/kronos/services
./start_gpu_simple.sh

# 2. 检查日志（另一个终端）
# 应该看到：
# - ⚠️  检测到 .env 文件，临时禁用以避免配置冲突
# - Service configuration: device=cuda:0

# 3. 验证设备
curl http://localhost:8000/v1/readyz | jq '.device'
# 应该返回：
# "cuda:0"

# 4. 停止服务（Ctrl+C）
# 应该看到：
# - 恢复 .env 文件...

# 5. 确认 .env 已恢复
ls -la /data/ws/kronos/services/kronos_fastapi/.env
# 应该存在
```

### 测试 CPU 模式

```bash
# 1. 启动 CPU 服务
cd /data/ws/kronos/services
./start_cpu_simple.sh

# 2. 验证设备
curl http://localhost:8000/v1/readyz | jq '.device'
# 应该返回：
# "cpu"
```

---

## 回退方案

如果新脚本有问题，可以临时使用旧版本：

```bash
# 手动禁用 .env
cd /data/ws/kronos/services/kronos_fastapi
mv .env .env.backup

# 使用任何启动脚本
cd /data/ws/kronos/services
./start_gpu_simple.sh
```

---

## 总结

**修改前：**
- ❌ .env 文件覆盖脚本的环境变量
- ❌ 启动 GPU 模式实际运行 CPU
- ❌ 需要手动删除 .env

**修改后：**
- ✅ 脚本自动处理 .env 冲突
- ✅ 配置完全由脚本控制
- ✅ 退出时自动恢复 .env
- ✅ 不影响 Docker 部署

**用户体验：**
- 开发者无需关心 .env 文件
- 脚本启动即可，自动处理冲突
- 退出时自动清理，无副作用

---

**相关文档：**
- 配置完整说明：`services/MANUAL_DEPLOYMENT_CONFIGS.md`
- 部署指南：`services/kronos_fastapi/DEPLOYMENT_DEVICE_OPTIONS.md`
