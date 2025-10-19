# Docker 部署快速启动指南

**快速参考卡 - 5 分钟上手 Docker 部署**

---

## 🚀 快速启动

### CPU 部署

```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-cpu.sh
```

### GPU 部署（推荐）

```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-gpu.sh
```

### 混合部署（CPU + GPU）

```bash
cd /data/ws/kronos/services/kronos_fastapi
./deploy-hybrid.sh --with-lb
```

---

## 📋 常用命令

### 查看状态

```bash
./deploy-cpu.sh --status      # CPU 部署状态
./deploy-gpu.sh --status      # GPU 部署状态
./deploy-hybrid.sh --status   # 混合部署状态
```

### 查看日志

```bash
./deploy-cpu.sh --logs        # CPU 日志
./deploy-gpu.sh --logs        # GPU 日志
./deploy-hybrid.sh --logs     # 混合部署日志
```

### 停止服务

```bash
./deploy-cpu.sh --stop        # 停止 CPU
./deploy-gpu.sh --stop        # 停止 GPU
./deploy-hybrid.sh --with-lb --stop  # 停止混合
```

### GPU 专用命令

```bash
./deploy-gpu.sh --check-gpu   # 检查 GPU 可用性
./deploy-gpu.sh --gpu-status  # 查看 GPU 使用情况
```

### 混合部署专用命令

```bash
./deploy-hybrid.sh --test     # 测试路由功能
```

---

## 🔍 验证部署

### 健康检查

```bash
# CPU 部署
curl http://kronos-api-cpu:8000/v1/healthz

# GPU 部署
curl http://kronos-api-gpu:8000/v1/healthz

# 混合部署（通过负载均衡器）
curl http://localhost:8080/v1/healthz
```

### 检查设备

```bash
# CPU 部署
curl http://kronos-api-cpu:8000/v1/readyz | jq '.device'
# 返回: "cpu"

# GPU 部署
curl http://kronos-api-gpu:8000/v1/readyz | jq '.device'
# 返回: "cuda:0"
```

---

## 🎯 三种部署方式对比

| 方式 | 启动命令 | 访问方式 | 适用场景 |
|------|---------|---------|---------|
| **CPU** | `./deploy-cpu.sh` | 容器内部 | 开发测试 |
| **GPU** | `./deploy-gpu.sh` | 容器内部 | 生产环境 |
| **混合** | `./deploy-hybrid.sh --with-lb` | http://localhost:8080 | 高可用 |

---

## 📦 使用 docker-compose（不用脚本）

### CPU 部署

```bash
cd /data/ws/kronos/services/kronos_fastapi
docker-compose -f docker-compose.cpu.yml up -d
docker-compose -f docker-compose.cpu.yml logs -f
docker-compose -f docker-compose.cpu.yml down
```

### GPU 部署

```bash
cd /data/ws/kronos/services/kronos_fastapi
docker-compose -f docker-compose.gpu.yml up -d
docker-compose -f docker-compose.gpu.yml logs -f
docker-compose -f docker-compose.gpu.yml down
```

### 混合部署

```bash
cd /data/ws/kronos/services/kronos_fastapi
# 带负载均衡器
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer up -d
docker-compose -f docker-compose.hybrid.yml logs -f
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer down
```

---

## 🔧 Docker 管理命令

### 查看运行容器

```bash
docker ps | grep kronos
```

### 查看所有容器（包括停止的）

```bash
docker ps -a | grep kronos
```

### 查看容器日志

```bash
docker logs kronos-api-cpu
docker logs kronos-api-gpu
docker logs kronos-nginx-lb
docker logs -f kronos-api-gpu  # 实时跟踪
```

### 进入容器

```bash
docker exec -it kronos-api-gpu bash
docker exec -it kronos-api-cpu bash
```

### 查看资源使用

```bash
docker stats kronos-api-gpu kronos-api-cpu
```

---

## 🐛 常见问题

### 1. GPU 部署失败

**检查：**
```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**解决：**
```bash
# 安装 NVIDIA Docker Runtime
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### 2. 端口冲突

**检查：**
```bash
sudo lsof -i :8080  # 检查负载均衡器端口
```

**解决：**
```bash
# 修改环境变量
export KRONOS_LB_PORT=8081
./deploy-hybrid.sh --with-lb
```

### 3. 容器启动失败

**检查日志：**
```bash
docker logs kronos-api-gpu
docker logs kronos-api-cpu
```

**重启容器：**
```bash
./deploy-gpu.sh --restart
```

---

## 🎓 进阶使用

### 自定义资源限制

编辑 `docker-compose.gpu.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'      # 增加 CPU 限制
      memory: 16G      # 增加内存限制
```

### 暴露端口到宿主机

编辑 `docker-compose.gpu.yml`:

```yaml
ports:
  - "8001:8000"  # 取消注释这行
```

### 使用不同 GPU

```bash
# 使用 GPU 1 而不是 GPU 0
export NVIDIA_VISIBLE_DEVICES=1
export KRONOS_DEVICE=cuda:1
./deploy-gpu.sh
```

---

## 📊 性能监控

### Prometheus 指标

```bash
curl http://kronos-api-gpu:8000/v1/metrics
```

### 实时监控

```bash
# 监控所有 Kronos 容器
watch -n 1 'docker stats --no-stream | grep kronos'

# 监控 GPU 使用
watch -n 1 'docker exec kronos-api-gpu nvidia-smi'
```

---

## 🔄 更新和维护

### 重新构建镜像

```bash
cd /data/ws/kronos/services/kronos_fastapi
docker-compose -f docker-compose.gpu.yml build --no-cache
```

### 清理旧容器和镜像

```bash
# 停止所有容器
docker-compose -f docker-compose.gpu.yml down

# 清理未使用的镜像
docker image prune -a
```

### 备份配置

```bash
# 备份配置文件
cp docker-compose.gpu.yml docker-compose.gpu.yml.backup
cp nginx.conf nginx.conf.backup
```

---

## 📚 相关文档

- **详细部署指南：** `DEPLOYMENT_DEVICE_OPTIONS.md`
- **配置说明：** `../MANUAL_DEPLOYMENT_CONFIGS.md`
- **开发模式：** `../DEV_MODE_NO_ENV.md`

---

## ⚡ 一键命令参考

```bash
# GPU 快速启动
cd /data/ws/kronos/services/kronos_fastapi && ./deploy-gpu.sh

# 查看 GPU 状态
./deploy-gpu.sh --gpu-status

# 查看日志
./deploy-gpu.sh --logs

# 停止服务
./deploy-gpu.sh --stop
```

---

**最后更新：** 2025-10-16
**维护者：** Kronos Team
