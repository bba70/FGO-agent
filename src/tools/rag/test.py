"""
RAG 模块简单测试
输入查询，查看检索和重排序结果
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.rag.rag import retrieve_documents, calculate_retrieval_quality
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_rag_retrieval(query: str, top_k: int = 3):
    """
    测试 RAG 检索功能
    
    Args:
        query: 用户查询
        top_k: 返回文档数量
    """
    print("\n" + "="*80)
    print(f"🔍 查询: {query}")
    print("="*80 + "\n")
    
    # 执行检索和重排序
    print("📊 正在检索文档...")
    documents = retrieve_documents(
        query=query,
        top_k=top_k,
        rerank=True,
        rerank_method="crossencoder"
    )
    
    # 计算检索质量
    quality_score = calculate_retrieval_quality(documents)
    
    # 输出结果
    print(f"\n✅ 检索完成！共找到 {len(documents)} 个相关文档")
    print(f"📈 检索质量分数: {quality_score:.3f}")
    
    # 质量评判
    if quality_score > 0.7:
        quality_label = "🟢 高质量 - 可直接使用"
    elif quality_score > 0.5:
        quality_label = "🟡 中等质量 - 可能需要改写查询"
    else:
        quality_label = "🔴 低质量 - 建议改写或切换到 Web 搜索"
    print(f"   判断: {quality_label}")
    
    # 输出每个文档的详细信息
    print("\n" + "-"*80)
    print("📄 检索结果详情:")
    print("-"*80)
    
    for i, doc in enumerate(documents, 1):
        print(f"\n【文档 {i}】")
        print(f"  从者: {doc['metadata'].get('servant_name', 'N/A')}")
        print(f"  类型: {doc['metadata'].get('chunk_type', 'N/A')}")
        print(f"  文档ID: {doc['id']}")
        print(f"  原始分数: {doc.get('score', 0):.3f}")
        if 'ce_score' in doc:
            print(f"  CrossEncoder分数: {doc['ce_score']:.3f}")
        print(f"  重排序分数: {doc.get('rerank_score', doc.get('score', 0)):.3f}")
        print(f"  内容预览: {doc['content'][:150]}...")
    
    print("\n" + "="*80 + "\n")
    
    return documents, quality_score


if __name__ == "__main__":
    # 测试查询
    test_queries = [
        "阿尔托莉雅的宝具是什么",
    ]
    
    # 如果有命令行参数，使用命令行参数作为查询
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        test_rag_retrieval(query, top_k=3)
    else:
        # 否则使用默认测试查询
        print("💡 提示: 可以通过命令行参数指定查询")
        print("   例如: python test_rag.py 玛修的宝具是什么\n")
        
        # 测试第一个查询作为示例
        test_rag_retrieval(test_queries[0], top_k=3)