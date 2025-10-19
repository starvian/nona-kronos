#!/usr/bin/env python3
"""
GPU 模式预测测试客户端 - 400→120 配置

对比 CPU vs GPU 性能
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any

import requests
import numpy as np


class KronosGPUTest400:
    """Kronos GPU 测试客户端 - 400→120 配置"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def check_ready(self) -> Dict[str, Any]:
        """检查模型就绪状态"""
        print("=" * 70)
        print("检查 GPU 模型就绪状态")
        print("=" * 70)
        
        response = self.session.get(f"{self.base_url}/v1/readyz", timeout=5)
        response.raise_for_status()
        result = response.json()
        
        print(f"状态: {result['status']}")
        print(f"模型已加载: {result['model_loaded']}")
        print(f"设备: {result.get('device', 'N/A')}")
        
        if result.get('device_warning'):
            print(f"⚠ 设备警告: {result['device_warning']}")
        
        if not result['model_loaded']:
            print("✗ 模型未加载，请等待...")
            return result
        
        if 'cuda' not in result.get('device', '').lower():
            print(f"⚠ 警告: 期望 GPU 设备，但得到: {result.get('device')}")
        else:
            print("✓ GPU 模型就绪")
        
        return result
    
    def generate_test_data(self, length: int = 400) -> Dict[str, Any]:
        """生成测试数据 - 400 点历史数据"""
        print("\n" + "=" * 70)
        print("生成测试数据")
        print("=" * 70)
        
        np.random.seed(42)
        base_price = 100.0
        
        returns = np.random.randn(length) * 0.02
        prices = base_price * np.exp(np.cumsum(returns))
        
        candles = []
        timestamps = []
        
        start_time = datetime(2024, 1, 1, 9, 30)
        
        for i in range(length):
            close = prices[i]
            
            high_offset = abs(np.random.randn() * 0.01)
            low_offset = abs(np.random.randn() * 0.01)
            
            open_price = close + (np.random.randn() * 0.005 * close)
            
            high = max(open_price, close) * (1 + high_offset)
            low = min(open_price, close) * (1 - low_offset)
            
            volume = abs(np.random.randn() * 1000000)
            
            candles.append({
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(volume),
                "amount": float(volume * close)
            })
            
            timestamps.append((start_time + timedelta(minutes=i)).isoformat())
        
        print(f"✓ 生成 {length} 条 K 线数据（历史输入）")
        
        return {
            "candles": candles,
            "timestamps": timestamps
        }
    
    def predict_gpu(
        self,
        candles: list,
        timestamps: list,
        pred_len: int = 120
    ) -> Dict[str, Any]:
        """执行 GPU 预测并统计时间"""
        print("\n" + "=" * 70)
        print(f"执行 GPU 预测 (400 → {pred_len})")
        print("=" * 70)
        
        last_time = datetime.fromisoformat(timestamps[-1])
        prediction_timestamps = [
            (last_time + timedelta(minutes=i+1)).isoformat()
            for i in range(pred_len)
        ]
        
        request_data = {
            "series_id": "test_gpu_400_120",
            "candles": candles,
            "timestamps": timestamps,
            "prediction_timestamps": prediction_timestamps,
            "overrides": {
                "pred_len": pred_len,
                "temperature": 1.0,
                "top_k": 0,
                "top_p": 0.9,
                "sample_count": 1
            }
        }
        
        print(f"请求参数:")
        print(f"  输入数据点: {len(candles)}")
        print(f"  预测长度: {pred_len}")
        print(f"  设备: GPU (Tesla M40)")
        print(f"\n开始预测...")
        
        start_time = time.time()
        
        response = self.session.post(
            f"{self.base_url}/v1/predict/single",
            json=request_data,
            timeout=120
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        if response.status_code != 200:
            print(f"\n✗ HTTP {response.status_code} 错误")
            print(f"响应: {response.text[:500]}")
        
        response.raise_for_status()
        result = response.json()
        
        print(f"\n✓ GPU 预测完成!")
        print(f"\n{'=' * 70}")
        print(f"⏱️  GPU 预测时间统计")
        print(f"{'=' * 70}")
        print(f"总耗时: {elapsed_time:.2f} 秒")
        print(f"平均每个预测点: {elapsed_time / pred_len:.3f} 秒")
        print(f"吞吐量: {pred_len / elapsed_time:.2f} 点/秒")
        
        return {
            "elapsed_time": elapsed_time,
            "pred_len": pred_len,
            "time_per_point": elapsed_time / pred_len,
            "throughput": pred_len / elapsed_time,
            "result": result
        }


def main():
    """主函数"""
    print("=" * 70)
    print("Kronos GPU 模式预测测试 - 400→120 配置")
    print("=" * 70)
    
    client = KronosGPUTest400(base_url="http://localhost:8000")
    
    try:
        # 1. 就绪检查
        ready_status = client.check_ready()
        
        if not ready_status.get('model_loaded'):
            print("\n请等待模型加载完成后重试")
            return
        
        # 2. 生成测试数据
        test_data = client.generate_test_data(length=400)
        
        # 3. GPU 预测
        gpu_result = client.predict_gpu(
            candles=test_data["candles"],
            timestamps=test_data["timestamps"],
            pred_len=120
        )
        
        # 4. 性能对比
        print("\n" + "=" * 70)
        print("📊 CPU vs GPU 性能对比")
        print("=" * 70)
        
        cpu_time = 32.86  # CPU 测试结果
        gpu_time = gpu_result["elapsed_time"]
        speedup = cpu_time / gpu_time
        
        print(f"\nCPU (FastAPI):")
        print(f"  总耗时: {cpu_time:.2f} 秒")
        print(f"  吞吐量: {120/cpu_time:.2f} 点/秒")
        
        print(f"\nGPU (FastAPI):")
        print(f"  总耗时: {gpu_time:.2f} 秒")
        print(f"  吞吐量: {gpu_result['throughput']:.2f} 点/秒")
        
        print(f"\nGPU 加速比: {speedup:.2f}x")
        
        if speedup > 5:
            print("  ✓ 显著加速！")
        elif speedup > 2:
            print("  ✓ 明显加速")
        else:
            print("  ⚠ 加速有限")
        
        # 保存结果
        output_file = "/data/ws/kronos/logs/test_gpu_400_120_result.json"
        with open(output_file, 'w') as f:
            json.dump({
                "test_config": {
                    "input_length": 400,
                    "pred_length": 120,
                    "device": "cuda:0 (Tesla M40)"
                },
                "performance": {
                    "gpu_time": gpu_time,
                    "cpu_time": cpu_time,
                    "speedup": speedup,
                    "throughput": gpu_result["throughput"]
                },
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        print(f"\n结果已保存到: {output_file}")
        
        print("\n" + "=" * 70)
        print("✓ GPU 测试完成")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
