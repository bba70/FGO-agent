"""
使用方法：
    python build_vectorstore.py              # 交互式构建
    python build_vectorstore.py --rebuild    # 直接重建（清空旧数据）
    python build_vectorstore.py --append     # 追加新数据
"""

import sys
import argparse
from pathlib import Path

# 确保项目路径正确
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.tools.rag.build_vectorstore import build_vectorstore


def print_banner():
    """打印欢迎横幅"""
    print("\n" + "="*80)
    print(" " * 20 + "🎮 FGO Agent - 向量数据库构建工具")
    print("="*80)
    print()
    print("📦 本次构建包含以下优化：")
    print()
    print("   1️⃣  Embedding 增强")
    print("      - 文档中重复从者名称（例如：玛修。玛修的素材。玛修）")
    print("      - 大幅提高从者名称在向量空间中的权重")
    print()
    print("   2️⃣  查询增强")
    print("      - 自动识别查询中的从者名称")
    print("      - 扩展查询以提高检索精度")
    print()
    print("   3️⃣  智能过滤")
    print("      - 先检索 10 个候选文档")
    print("      - 基于从者名称精确过滤，只保留匹配的前 5 个")
    print()
    print("   4️⃣  阈值优化")
    print("      - 质量分数阈值：0.6 → 0.4")
    print("      - 提高召回率，减少漏检")
    print()
    print("="*80)


def print_tips():
    """打印使用提示"""
    print("\n💡 使用提示：")
    print()
    print("   📁 数据源：data/textarea/*.txt")
    print("   📦 存储位置：data/vectorstore/chromaDB/")
    print("   🔧 配置文件：database/kb/vectordb.py")
    print()
    print("   ⏱️  构建时间：取决于从者数量和网络速度")
    print("   💾 磁盘空间：约 100-500MB（取决于数据量）")
    print()
    print("="*80)


def confirm_rebuild():
    """确认是否重建"""
    print("\n⚠️  注意：重建将清空现有向量数据库！")
    print()
    response = input("❓ 确认继续？(y/n): ").strip().lower()
    return response == 'y'


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="FGO Agent 向量数据库构建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python build_vectorstore.py              # 交互式构建
  python build_vectorstore.py --rebuild    # 直接重建
  python build_vectorstore.py --append     # 追加数据
        """
    )
    
    parser.add_argument(
        '--rebuild',
        action='store_true',
        help='直接重建数据库（清空旧数据，无需确认）'
    )
    
    parser.add_argument(
        '--append',
        action='store_true',
        help='追加数据（保留旧数据）'
    )
    
    parser.add_argument(
        '--no-test',
        action='store_true',
        help='跳过测试检索'
    )
    
    args = parser.parse_args()
    
    # 打印横幅
    print_banner()
    print_tips()
    
    # 如果是交互模式，询问用户
    if not args.rebuild and not args.append:
        print("\n📋 构建模式选择：")
        print()
        print("   1️⃣  重建 - 清空现有数据，重新构建")
        print("   2️⃣  追加 - 保留现有数据，追加新数据")
        print("   3️⃣  取消")
        print()
        
        choice = input("请选择 (1/2/3): ").strip()
        
        if choice == '1':
            if not confirm_rebuild():
                print("\n❌ 已取消构建")
                return
        elif choice == '2':
            print("\n✅ 将追加新数据")
        else:
            print("\n❌ 已取消构建")
            return
    
    # 执行构建
    try:
        print("\n" + "="*80)
        print("🚀 开始构建向量数据库...")
        print("="*80)
        
        build_vectorstore()
        
        print("\n" + "="*80)
        print("✅ 构建完成！")
        print("="*80)
        print()
        print("📌 下一步：")
        print("   1. 启动 Web 服务：python start_web.py 或 start_web.bat")
        print("   2. 访问：http://localhost:8000")
        print("   3. 测试查询：玛修的升级素材、阿尔托莉雅的宝具效果")
        print()
        print("="*80)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n\n❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

