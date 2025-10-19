# Docker 构建修复说明

**问题：** Docker 构建失败，找不到 model 目录

**原因：** Dockerfile 中的路径引用不正确（使用了相对路径 `../../`）

**解决：** 已修复为绝对路径（相对于构建上下文）

---

## 已修复的问题

### 1. 文件路径修复

**修改前（错误）：**
```dockerfile
COPY requirements.txt ./
COPY ../../requirements.txt ./core-requirements.txt
COPY --chown=kronos:kronos ../../model ./model
COPY --chown=kronos:kronos . ./services/kronos_fastapi
```

**修改后（正确）：**
```dockerfile
COPY services/kronos_fastapi/requirements.txt ./
COPY gitSource/requirements.txt ./core-requirements.txt
COPY --chown=kronos:kronos gitSource/model ./model
COPY --chown=kronos:kronos services/kronos_fastapi ./services/kronos_fastapi
```

### 2. 构建上下文

`docker-compose.*.yml` 中的构建上下文：
```yaml
build:
  context: ../..  # 指向 /data/ws/kronos
  dockerfile: services/kronos_fastapi/Dockerfile
```

这意味着 Dockerfile 中的路径是相对于 `/data/ws/kronos` 的，所以：
- ✅ `gitSource/model` = `/data/ws/kronos/gitSource/model`
- ✅ `services/kronos_fastapi` = `/data/ws/kronos/services/kronos_fastapi`

---

## 首次构建时间

**预计时间：** 5-10 分钟

**主要耗时：**
1. 下载 PyTorch：~888 MB（约 1-2 分钟）
2. 下载 CUDA 库：~594 MB（约 1 分钟）
3. 下载其他依赖：~50 MB（约 30 秒）
4. 安装所有包：约 2-3 分钟
5. 复制应用代码：约 30 秒

**总计：** 约 5-10 分钟（取决于网速）

---

## 如何使用

### 方式 1：使用部署脚本（推荐）

```bash
cd /data/ws/kronos/services/kronos_fastapi

# CPU 部署
./deploy-cpu.sh

# GPU 部署
./deploy-gpu.sh

# 混合部署
./deploy-hybrid.sh --with-lb
```

### 方式 2：使用 docker-compose

```bash
cd /data/ws/kronos/services/kronos_fastapi

# CPU 部署
docker-compose -f docker-compose.cpu.yml up -d

# GPU 部署
docker-compose -f docker-compose.gpu.yml up -d

# 混合部署
docker-compose -f docker-compose.hybrid.yml --profile loadbalancer up -d
```

---

## 构建进度监控

### 实时查看构建日志

```bash
# 使用 docker-compose
docker-compose -f docker-compose.cpu.yml up --build

# 或查看构建进度
docker-compose -f docker-compose.cpu.yml build --progress=plain
```

### 构建阶段说明

```
Stage 1: Builder (安装依赖)
  ├─ [1/7] 安装系统依赖
  ├─ [2/7] 创建虚拟环境
  ├─ [3/7] 复制 requirements 文件
  ├─ [4/7] 安装 core requirements（PyTorch, CUDA）← 最慢
  └─ [5/7] 安装 service requirements

Stage 2: Runtime (最终镜像)
  ├─ [1/8] 安装运行时依赖
  ├─ [2/8] 创建用户和目录
  ├─ [3/8] 复制虚拟环境
  ├─ [4/8] 复制 model 代码
  └─ [5/8] 复制 service 代码
```

---

## 加速后续构建

### Docker 缓存

Docker 会缓存每一层，后续构建会快得多：

**首次构建：** 5-10 分钟
**后续构建（代码修改）：** 30 秒 - 1 分钟

### 只重建修改的部分

如果只修改了应用代码（不修改依赖），Docker 会复用缓存：

```bash
# 快速重建（利用缓存）
docker-compose -f docker-compose.cpu.yml build

# 强制完全重建（不用缓存）
docker-compose -f docker-compose.cpu.yml build --no-cache
```

---

## 故障排查

### 1. 构建超时

```bash
# 手动构建，不使用脚本
cd /data/ws/kronos/services/kronos_fastapi
docker-compose -f docker-compose.cpu.yml build --progress=plain

# 查看详细进度
```

### 2. 网络问题

如果下载速度慢，可以配置 Docker 使用国内镜像：

```bash
# 编辑 /etc/docker/daemon.json
sudo nano /etc/docker/daemon.json

# 添加：
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}

# 重启 Docker
sudo systemctl restart docker
```

### 3. 空间不足

```bash
# 检查磁盘空间
df -h

# 清理未使用的 Docker 资源
docker system prune -a --volumes

# 查看 Docker 占用空间
docker system df
```

### 4. 构建失败

```bash
# 查看完整构建日志
docker-compose -f docker-compose.cpu.yml build --progress=plain 2>&1 | tee build.log

# 检查最后的错误
tail -100 build.log
```

---

## 验证构建成功

### 1. 检查镜像

```bash
docker images | grep kronos
```

预期输出：
```
kronos-fastapi   cpu    xxx   5 minutes ago   2.5GB
kronos-fastapi   gpu    xxx   5 minutes ago   2.5GB
```

### 2. 测试运行

```bash
# 启动容器
./deploy-cpu.sh

# 检查健康状态
docker ps | grep kronos

# 查看日志
./deploy-cpu.sh --logs
```

### 3. 验证服务

```bash
# 健康检查
curl http://kronos-api-cpu:8000/v1/healthz

# 就绪检查
curl http://kronos-api-cpu:8000/v1/readyz
```

---

## 当前状态

✅ Dockerfile 路径已修复
✅ 脚本换行符已修复
⏳ 首次构建正在进行中（需要 5-10 分钟）

**建议：** 让构建继续运行，第一次需要下载和安装所有依赖。

---

## 构建完成后

构建成功后，你可以：

1. **查看运行的容器：**
   ```bash
   docker ps | grep kronos
   ```

2. **测试服务：**
   ```bash
   curl http://kronos-api-cpu:8000/v1/readyz | jq .
   ```

3. **查看日志：**
   ```bash
   ./deploy-cpu.sh --logs
   ```

4. **停止服务：**
   ```bash
   ./deploy-cpu.sh --stop
   ```

---

**修复时间：** 2025-10-16
**状态：** ✅ 路径修复完成，构建中...
