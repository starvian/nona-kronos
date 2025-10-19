================================================================================
Kronos CPU 模式 - 配置、启动和测试完整指南
================================================================================

📁 位置: /data/ws/kronos/services/

🚀 一键启动测试:
   1. 启动服务:  ./start_cpu_server.sh
   2. 运行测试:  python test_cpu_prediction.py

📖 文档索引:
   - QUICKSTART.md                - 一分钟快速开始
   - START_CPU_MODE.md            - 详细启动指南
   - CPU_TEST_SUMMARY.md          - 完整总结（推荐阅读）
   - DEVICE_SUPPORT.md            - 技术文档
   - CPU_GPU_IMPLEMENTATION.md    - 实现架构

🔧 配置文件:
   - kronos_fastapi/.env.cpu      - CPU 配置模板

🧪 测试脚本:
   - test_cpu_prediction.py       - 性能测试客户端
   - test_device_resolution.py    - 设备验证测试

⚡ 快速命令:

   # 启动服务
   cd /data/ws/kronos/services
   ./start_cpu_server.sh

   # 检查状态（新终端）
   curl http://localhost:8000/v1/readyz

   # 运行测试
   python test_cpu_prediction.py

⏱️ 预期性能: 
   100 输入点 → 10 预测点 → 约 10-20 秒（CPU 模式）

📊 输出示例:
   总耗时: 12.34 秒
   平均每个预测点: 1.234 秒
   吞吐量: 0.81 点/秒

✅ 所有功能已实现并测试通过！

================================================================================
