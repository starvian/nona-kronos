#!/usr/bin/env python3
"""
CPU 模式预测测试客户端

测试 Kronos FastAPI 服务的 CPU 推理性能。
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any

import requests
import pandas as pd
import numpy as np


class KronosCPUTestClient:
    """Kronos CPU 测试客户端"""
    
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
    
    def generate_test_data(self, length: int = 100) -> Dict[str, Any]:
        """生成测试数据"""
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
        
        print(f"✓ 生成 {length} 条 K 线数据")
        print(f"  时间范围: {timestamps[0]} 到 {timestamps[-1]}")
        print(f"  价格范围: {min(prices):.2f} - {max(prices):.2f}")
        
        return {
            "candles": candles,
            "timestamps": timestamps
        }
    
    def predict_single(
        self,
        candles: list,
        timestamps: list,
        pred_len: int = 10,
        temperature: float = 1.0,
        sample_count: int = 1
    ) -> Dict[str, Any]:
        """执行单次预测并统计时间"""
        print("\n" + "=" * 70)
        print("4. 执行 CPU 预测")
        print("=" * 70)
        
        # 生成未来时间戳
        last_time = datetime.fromisoformat(timestamps[-1])
        prediction_timestamps = [
            (last_time + timedelta(minutes=i+1)).isoformat()
            for i in range(pred_len)
        ]
        
        # 构建请求（所有 overrides 字段都必须提供）
        request_data = {
            "series_id": "test_cpu_prediction",
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
        print(f"\n开始预测...")
        
        # 开始计时
        start_time = time.time()
        
        try:
            response = self.session.post(
                f"{self.base_url}/v1/predict/single",
                json=request_data,
                timeout=180  # CPU 模式需要更长超时
            )
            
            # 结束计时
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # 检查响应状态
            if response.status_code != 200:
                print(f"\n✗ HTTP {response.status_code} 错误")
                print(f"响应内容: {response.text}")
            
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
                predictions = result['prediction'][:3]  # 显示前3个
                print(f"\n预测结果（前3个点）:")
                for i, pred in enumerate(predictions, 1):
                    print(f"  {i}. 时间: {pred['timestamp']}")
                    print(f"     OHLC: O={pred['open']:.2f}, H={pred['high']:.2f}, "
                          f"L={pred['low']:.2f}, C={pred['close']:.2f}")
            
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
            raise
        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\n✗ 预测失败 (耗时 {elapsed_time:.2f} 秒): {e}")
            raise
    
    def run_performance_test(
        self,
        input_lengths: list = [50, 100],
        pred_lengths: list = [5, 10],
        sample_counts: list = [1, 3]
    ):
        """运行性能测试套件"""
        print("\n" + "=" * 70)
        print("5. CPU 性能测试套件")
        print("=" * 70)
        
        results = []
        
        for input_len in input_lengths:
            for pred_len in pred_lengths:
                for sample_count in sample_counts:
                    print(f"\n{'─' * 70}")
                    print(f"测试配置: 输入={input_len}, 预测={pred_len}, 采样={sample_count}")
                    print(f"{'─' * 70}")
                    
                    # 生成数据
                    test_data = self.generate_test_data(input_len)
                    
                    # 执行预测
                    try:
                        result = self.predict_single(
                            candles=test_data["candles"],
                            timestamps=test_data["timestamps"],
                            pred_len=pred_len,
                            sample_count=sample_count
                        )
                        
                        results.append({
                            "input_length": input_len,
                            "pred_length": pred_len,
                            "sample_count": sample_count,
                            "elapsed_time": result["elapsed_time"],
                            "time_per_point": result["time_per_point"],
                            "throughput": result["throughput"],
                            "status": "success"
                        })
                        
                        time.sleep(1)  # 间隔1秒
                        
                    except Exception as e:
                        print(f"✗ 测试失败: {e}")
                        results.append({
                            "input_length": input_len,
                            "pred_length": pred_len,
                            "sample_count": sample_count,
                            "status": "failed",
                            "error": str(e)
                        })
        
        # 打印汇总
        print("\n" + "=" * 70)
        print("📊 性能测试汇总")
        print("=" * 70)
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            success_df = df[df['status'] == 'success']
            
            if not success_df.empty:
                print("\n成功的测试:")
                print(success_df.to_string(index=False))
                
                print(f"\n统计摘要:")
                print(f"  平均预测时间: {success_df['elapsed_time'].mean():.2f} 秒")
                print(f"  最快: {success_df['elapsed_time'].min():.2f} 秒")
                print(f"  最慢: {success_df['elapsed_time'].max():.2f} 秒")
                print(f"  平均吞吐量: {success_df['throughput'].mean():.2f} 点/秒")
            
            failed_df = df[df['status'] == 'failed']
            if not failed_df.empty:
                print(f"\n失败的测试: {len(failed_df)}")
        
        return results


def main():
    """主函数"""
    print("=" * 70)
    print("Kronos CPU 模式预测测试")
    print("=" * 70)
    
    # 创建客户端
    client = KronosCPUTestClient(base_url="http://localhost:8000")
    
    try:
        # 1. 健康检查
        client.check_health()
        
        # 2. 就绪检查
        ready_status = client.check_ready()
        
        if not ready_status.get('model_loaded'):
            print("\n请等待模型加载完成后重试")
            return
        
        # 3. 生成测试数据
        test_data = client.generate_test_data(length=100)
        
        # 4. 单次预测测试
        result = client.predict_single(
            candles=test_data["candles"],
            timestamps=test_data["timestamps"],
            pred_len=10,
            sample_count=1
        )
        
        # 5. 可选：运行完整性能测试（取消注释启用）
        # print("\n是否运行完整性能测试？这将需要较长时间。")
        # response = input("输入 'yes' 继续: ")
        # if response.lower() == 'yes':
        #     client.run_performance_test(
        #         input_lengths=[50, 100],
        #         pred_lengths=[5, 10],
        #         sample_counts=[1]
        #     )
        
        print("\n" + "=" * 70)
        print("✓ 测试完成")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
