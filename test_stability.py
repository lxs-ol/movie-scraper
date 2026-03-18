#!/usr/bin/env python3
"""
稳定性测试脚本
测试应用程序的关键功能，确保不会崩溃
"""

import subprocess
import time
import os


def test_application_start():
    """测试应用程序启动"""
    print("测试应用程序启动...")
    try:
        # 启动应用程序
        process = subprocess.Popen(
            ["build_final\\Movie Scraper.exe"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        # 等待应用程序启动
        time.sleep(5)
        
        # 检查进程是否运行
        if process.poll() is None:
            print("✓ 应用程序启动成功")
            # 等待一段时间后关闭
            time.sleep(10)
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return True
        else:
            print("✗ 应用程序启动失败")
            return False
    except Exception as e:
        print(f"✗ 启动测试失败: {e}")
        return False


def test_multiple_starts():
    """测试多次启动应用程序"""
    print("测试多次启动应用程序...")
    try:
        for i in range(3):
            print(f"  启动第 {i+1} 次...")
            process = subprocess.Popen(
                ["build_final\\Movie Scraper.exe"],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            time.sleep(3)
            
            if process.poll() is None:
                print(f"  ✓ 第 {i+1} 次启动成功")
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            else:
                print(f"  ✗ 第 {i+1} 次启动失败")
                return False
            
            time.sleep(2)
        
        print("✓ 多次启动测试通过")
        return True
    except Exception as e:
        print(f"✗ 多次启动测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始稳定性测试...")
    print("=" * 50)
    
    tests = [
        ("应用程序启动", test_application_start),
        ("多次启动测试", test_multiple_starts),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n测试: {test_name}")
        if test_func():
            passed += 1
        print("-" * 30)
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过，应用程序稳定性良好")
    else:
        print("✗ 部分测试失败，需要进一步检查")


if __name__ == "__main__":
    main()
