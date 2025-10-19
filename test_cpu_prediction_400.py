#!/usr/bin/env python3
"""
CPU 模式预测测试客户端 - 400→120 配置（对标原始 example）

完全对应原始 prediction_example.py 的配置：
- 输入长度: 400 点
- 预测长度: 120 点
- 采样次数: 1
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any

import requests
import pandas as pd
import numpy as np


class KronosCPUTest400:
    """Kronos CPU 测试客户端 - 400→120 配置"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def check_health(self) -> Dict[str, Any]:
        """检查服务健康状态"""
        print("=" * 70)
        print("1. 检查服务健康状态")
        print("=" * 70)
        
        try:
            response = self.session.get(f"{self.base_url}/v1/healthz", timeout=5)
            response.raise_for_status()
            result = response.json()
            print(f"✓ 服务健康: {result}")
            return result
        except Exception as e:
            print(f"✗ 健康检查失败: {e}")
            raise
    
    def check_ready(self) -> Dict[str, Any]:
        """检查模型就绪状态"""
        print("\n" + "=" * 70)
        print("2. 检查模型就绪状态")
        print("=" * 70)
        
        try:
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
            
            print("✓ 模型就绪")
            return result
        except Exception as e:
            print(f"✗ 就绪检查失败: {e}")
            raise
    
    def generate_test_data(self, length: int = 400) -> Dict[str, Any]:
        """生成测试数据 - 400 点历史数据"""
        print("\n" + "=" * 70)
        print("3. 生成测试数据")
        print("=" * 70)
        
        # 生成模拟的 OHLCV 数据
        np.random.seed(42)
        base_price = 100.0
        
        # 随机游走生成价格
        returns = np.random.randn(length) * 0.02
        prices = base_price * np.exp(np.cumsum(returns))
        
        # 生成 OHLCV
        candles = []
        timestamps = []
        
        start_time = datetime(2024, 1, 1, 9, 30)
        
        for i in range(length):
            close = prices[i]
            
            # 生成 high 和 low（确保符合逻辑）
            high_offset = abs(np.random.randn() * 0.01)
            low_offset = abs(np.random.randn() * 0.01)
            
            # open 在 low 和 high 之间
            open_price = close + (np.random.randn() * 0.005 * close)
            
            # 确保 high >= max(open, close) 且 low <= min(open, close)
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
        print(f"  时间范围: {timestamps[0]} 到 {timestamps[-1]}")
        print(f"  价格范围: {min(prices):.2f} - {max(prices):.2f}")
        
        return {
            "candles": candles,
            "timestamps": timestamps
        }
    
    def predict_long_sequence(
        self,
        candles: list,
        timestamps: list,
        pred_len: int = 120,
        temperature: float = 1.0,
        sample_count: int = 1
    ) -> Dict[str, Any]:
        """执行长序列预测（400→120）并统计时间"""
        print("\n" + "=" * 70)
        print("4. 执行 CPU 长序列预测 (400 → 120)")
        print("=" * 70)
        
        # 生成未来时间戳
        last_time = datetime.fromisoformat(timestamps[-1])
        prediction_timestamps = [
            (last_time + timedelta(minutes=i+1)).isoformat()
            for i in range(pred_len)
        ]
        
        # 构建请求
        request_data = {
            "series_id": "test_cpu_400_120",
            "candles": candles,
            "timestamps": timestamps,
            "prediction_timestamps": prediction_timestamps,
            "overrides": {
                "pred_len": pred_len,
                "temperature": temperature,
                "top_k": 0,
                "top_p": 0.9,
                "sample_count": sample_count
            }
        }
        
        print(f"请求参数:")
        print(f"  输入数据点: {len(candles)}")
        print(f"  预测长度: {pred_len}")
        print(f"  Temperature: {temperature}")
        print(f"  采样次数: {sample_count}")
        print(f"\n⚠️  警告: 长序列预测可能需要较长时间（预估 20-30 秒）")
        print(f"开始预测...")
        
        # 开始计时
        start_time = time.time()
        
        try:
            response = self.session.post(
                f"{self.base_url}/v1/predict/single",
                json=request_data,
                timeout=300  # 5分钟超时
            )
            
            # 结束计时
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # 检查响应状态
            if response.status_code != 200:
                print(f"\n✗ HTTP {response.status_code} 错误")
                print(f"响应内容: {response.text[:500]}")
            
            response.raise_for_status()
            result = response.json()
            
            print(f"\n✓ 预测完成!")
            print(f"\n{'=' * 70}")
            print(f"⏱️  预测时间统计")
            print(f"{'=' * 70}")
            print(f"总耗时: {elapsed_time:.2f} 秒")
            print(f"平均每个预测点: {elapsed_time / pred_len:.3f} 秒")
            print(f"吞吐量: {pred_len / elapsed_time:.2f} 点/秒")
            
            # 显示预测结果样例
            if result.get('prediction'):
                predictions = result['prediction']
                print(f"\n预测结果样本（前3个点）:")
                for i, pred in enumerate(predictions[:3], 1):
                    print(f"  {i}. 时间: {pred['timestamp']}")
                    print(f"     OHLC: O={pred['open']:.2f}, H={pred['high']:.2f}, "
                          f"L={pred['low']:.2f}, C={pred['close']:.2f}")
                
                print(f"\n预测结果样本（最后3个点）:")
                for i, pred in enumerate(predictions[-3:], len(predictions)-2):
                    print(f"  {i}. 时间: {pred['timestamp']}")
                    print(f"     OHLC: O={pred['open']:.2f}, H={pred['high']:.2f}, "
                          f"L={pred['low']:.2f}, C={pred['close']:.2f}")
            
            # 与原始 example 对比
            print(f"\n{'=' * 70}")
            print(f"📊 与原始 prediction_example.py 对比")
            print(f"{'=' * 70}")
            print(f"原始 example (直接调用模型):")
            print(f"  配置: 400 输入 → 120 预测")
            print(f"  设备: CPU")
            print(f"  耗时: 25.87 秒")
            print(f"  吞吐: 4.64 点/秒")
            print(f"\n当前测试 (FastAPI 服务):")
            print(f"  配置: {len(candles)} 输入 → {pred_len} 预测")
            print(f"  设备: CPU")
            print(f"  耗时: {elapsed_time:.2f} 秒")
            print(f"  吞吐: {pred_len / elapsed_time:.2f} 点/秒")
            
            # 计算差异
            original_time = 25.87
            speedup = original_time / elapsed_time if elapsed_time > 0 else 0
            overhead = ((elapsed_time - original_time) / original_time * 100) if original_time > 0 else 0
            
            print(f"\n性能对比:")
            if speedup > 1:
                print(f"  ✓ FastAPI 更快: {speedup:.2f}x")
            elif speedup < 1:
                print(f"  ⚠ FastAPI 较慢: {1/speedup:.2f}x")
                print(f"  ⚠ 开销: {overhead:.1f}%")
                print(f"     （包含网络请求、序列化等额外开销）")
            else:
                print(f"  ≈ 性能相当")
            
            return {
                "elapsed_time": elapsed_time,
                "pred_len": pred_len,
                "time_per_point": elapsed_time / pred_len,
                "throughput": pred_len / elapsed_time,
                "result": result
            }
            
        except requests.exceptions.Timeout:
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\n✗ 请求超时 (耗时 {elapsed_time:.2f} 秒)")
            print(f"提示: 长序列预测可能需要更长时间，请考虑:")
            print(f"  1. 增加超时时间")
            print(f"  2. 减少预测长度")
            print(f"  3. 使用 GPU 加速")
            raise
        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\n✗ 预测失败 (耗时 {elapsed_time:.2f} 秒): {e}")
            raise


def main():
    """主函数"""
    print("=" * 70)
    print("Kronos CPU 模式预测测试 - 400→120 配置")
    print("对标原始 prediction_example.py")
    print("=" * 70)
    
    # 创建客户端
    client = KronosCPUTest400(base_url="http://localhost:8000")
    
    try:
        # 1. 健康检查
        client.check_health()
        
        # 2. 就绪检查
        ready_status = client.check_ready()
        
        if not ready_status.get('model_loaded'):
            print("\n请等待模型加载完成后重试")
            return
        
        # 3. 生成测试数据 (400 点)
        test_data = client.generate_test_data(length=400)
        
        # 4. 长序列预测测试 (400 → 120)
        print("\n" + "⚠" * 35)
        print("注意: 此测试将预测 120 个点，预计需要 20-30 秒")
        print("请耐心等待...")
        print("⚠" * 35)
        
        result = client.predict_long_sequence(
            candles=test_data["candles"],
            timestamps=test_data["timestamps"],
            pred_len=120,
            temperature=1.0,
            sample_count=1
        )
        
        print("\n" + "=" * 70)
        print("✓ 测试完成")
        print("=" * 70)
        
        # 保存结果
        output_file = "/data/ws/kronos/logs/test_400_120_result.json"
        with open(output_file, 'w') as f:
            json.dump({
                "test_config": {
                    "input_length": 400,
                    "pred_length": 120,
                    "sample_count": 1,
                    "device": "cpu"
                },
                "performance": {
                    "elapsed_time": result["elapsed_time"],
                    "time_per_point": result["time_per_point"],
                    "throughput": result["throughput"]
                },
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        print(f"\n结果已保存到: {output_file}")
        
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
