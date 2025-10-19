# 脚本文件修复说明

**问题：** 脚本无法执行，提示 "cannot execute: required file not found"

**原因：** 脚本文件使用了 Windows 风格的换行符（CRLF），Linux 无法执行

**解决：** 已转换所有脚本为 Unix 格式（LF）

---

## 已修复的脚本

### Docker 部署脚本

- ✅ `services/kronos_fastapi/deploy-cpu.sh`
- ✅ `services/kronos_fastapi/deploy-gpu.sh`
- ✅ `services/kronos_fastapi/deploy-hybrid.sh`

### 开发启动脚本

- ✅ `services/start_cpu_simple.sh`
- ✅ `services/start_cpu_simple_v2.sh`
- ✅ `services/start_gpu_simple.sh`

---

## 现在可以正常使用

### Docker 部署

```bash
cd /data/ws/kronos/services/kronos_fastapi

# 测试脚本
./deploy-cpu.sh --help
./deploy-gpu.sh --help
./deploy-hybrid.sh --help

# 启动服务
./deploy-cpu.sh
./deploy-gpu.sh
./deploy-hybrid.sh --with-lb
```

### 开发模式

```bash
cd /data/ws/kronos/services

# 启动 CPU
./start_cpu_simple.sh

# 启动 GPU
./start_gpu_simple.sh
```

---

## 如果以后遇到类似问题

### 诊断方法

```bash
# 检查文件格式
file script.sh

# 如果看到 "CRLF line terminators" 就是换行符问题
```

### 修复方法

```bash
# 方法 1：使用 dos2unix（推荐）
dos2unix script.sh

# 方法 2：使用 sed
sed -i 's/\r$//' script.sh

# 方法 3：批量修复
dos2unix *.sh
```

---

## 预防措施

在创建脚本时，确保编辑器使用 Unix 换行符（LF）：

- **VSCode**: 右下角点击 "CRLF"，选择 "LF"
- **Vim**: `:set fileformat=unix`
- **Nano**: 保存时会自动使用 Unix 格式

---

**修复时间：** 2025-10-16
**状态：** ✅ 所有脚本已修复并可正常使用
