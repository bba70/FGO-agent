#!/usr/bin/env python3
"""
FGO Agent Web 服务启动脚本
"""
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """检查必要的依赖"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'websockets',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ 缺少以下依赖包: {', '.join(missing)}")
        print(f"请运行: pip install {' '.join(missing)}")
        return False
    
    return True

def main():
    """主函数"""
    print("🎮 FGO Agent Web 服务启动器")
    print("=" * 60)
    
    # 检查依赖
    print("\n🔍 检查依赖包...")
    if not check_dependencies():
        sys.exit(1)
    
    print("✅ 依赖检查通过")
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    api_dir = project_root / "api"
    
    if not api_dir.exists():
        print(f"❌ 找不到 API 目录: {api_dir}")
        sys.exit(1)
    
    print(f"\n📁 项目目录: {project_root}")
    print(f"📁 API 目录: {api_dir}")
    
    # 启动 FastAPI 服务器
    print("\n🚀 启动 FastAPI 服务器...")
    print("=" * 60)
    print("📍 访问地址: http://localhost:8000")
    print("📚 API 文档: http://localhost:8000/docs")
    print("=" * 60)
    print("\n按 Ctrl+C 停止服务器\n")
    
    try:
        # 切换到 api 目录
        import os
        os.chdir(api_dir)
        
        # 启动 uvicorn
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

