# from llm.router import ModelRouter
# import asyncio


# async def test_stream():
#     """测试流式输出"""
#     print("=" * 50)
#     print("测试流式输出")
#     print("=" * 50)
    
#     router = ModelRouter(config_path="llm/config.yaml")
#     stream_result = await router.chat(
#         model="fgo-chat-model",
#         messages=[{"role": "user", "content": "你好，请用一句话介绍一下自己"}],
#         stream=True,
#     )
    
#     # stream_result 现在是 StreamWithMetadata 对象
#     print("流式输出：", end="")
#     async for chunk in stream_result:
#         content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
#         if content:
#             print(content, end="", flush=True)
    
#     print("\n")
#     # 流式传输完成后，可以获取元数据（通过闭包变量）
#     if hasattr(stream_result, '_metadata_dict'):
#         instance_name = stream_result._metadata_dict.get('instance_name')
#         physical_model_name = stream_result._metadata_dict.get('physical_model_name')
#         print(f"使用的实例: {instance_name}")
#         print(f"物理模型: {physical_model_name}")


# async def test_non_stream():
#     """测试非流式输出"""
#     print("\n" + "=" * 50)
#     print("测试非流式输出")
#     print("=" * 50)
    
#     router = ModelRouter(config_path="llm/config.yaml")
#     result, instance_name, physical_model_name, failover_events = await router.chat(
#         model="fgo-chat-model",
#         messages=[{"role": "user", "content": "你好"}],
#         stream=False,
#     )
    
#     # 打印结果
#     content = result.get("choices", [{}])[0].get("message", {}).get("content")
#     print(f"回复: {content}")
#     print(f"使用的实例: {instance_name}")
#     print(f"物理模型: {physical_model_name}")
#     print(f"Token 使用: {result.get('usage', {})}")
#     print(f"容灾事件: {failover_events}")


# async def main():
#     """主测试函数"""
#     # 测试流式
#     await test_stream()
    
#     # 测试非流式
#     await test_non_stream()


# if __name__ == "__main__":
#     asyncio.run(main())



# """
# 测试 parse.py 的输出结构
# """


# import json
# from data.parse_wiki import parse_full_wikitext

# # 读取一个示例文件
# with open('data/textarea/阿尔托莉雅·潘德拉贡.txt', 'r', encoding='utf-8') as f:
#     wikitext_content = f.read()

# # 解析
# parsed_data = parse_full_wikitext(wikitext_content)

# # 打印JSON结构
# print(json.dumps(parsed_data, indent=2, ensure_ascii=False))

# # 打印结构概览
# print("\n" + "="*80)
# print("数据结构概览：")
# print("="*80)
# for key, value in parsed_data.items():
#     if isinstance(value, dict):
#         print(f"\n【{key}】 (字典)")
#         for k, v in list(value.items())[:3]:  # 只显示前3个
#             print(f"  {k}: {str(v)[:50]}...")
#     elif isinstance(value, list):
#         print(f"\n【{key}】 (列表, 长度: {len(value)})")
#         if value:
#             print(f"  第一项类型: {type(value[0])}")
#             if isinstance(value[0], dict):
#                 print(f"  第一项的键: {list(value[0].keys())}")
#     else:
#         print(f"\n【{key}】: {str(value)[:50]}")


from src.tools.rag.build_vectorstore import build_vectorstore

build_vectorstore()

# """
# RAG 检索和重排序功能测试
# """
# import sys
# import logging
# from pathlib import Path

# # 添加项目根目录到 Python 路径
# project_root = Path(__file__).parent.parent.parent.parent
# sys.path.insert(0, str(project_root))

# from src.tools.rag.rag import (
#     RAGRetriever,
#     retrieve_documents,
#     calculate_retrieval_quality
# )

# # 配置日志
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)


# def test_vectordb_connection():
#     """测试 1: 向量数据库连接"""
#     print("\n" + "="*60)
#     print("测试 1: 向量数据库连接")
#     print("="*60)
    
#     try:
#         retriever = RAGRetriever()
#         collection = retriever.vectordb.get_collection("fgo_servants")
#         count = collection.count()
#         print(f"✅ 向量数据库连接成功")
#         print(f"📊 集合名称: fgo_servants")
#         print(f"📊 文档数量: {count}")
#         return True
#     except Exception as e:
#         print(f"❌ 向量数据库连接失败: {str(e)}")
#         return False


# def test_basic_retrieval():
#     """测试 2: 基本检索（不重排序）"""
#     print("\n" + "="*60)
#     print("测试 2: 基本检索（不重排序）")
#     print("="*60)
    
#     test_queries = [
#         "玛修的宝具是什么",
#         "阿尔托莉雅的技能",
#         "吉尔伽美什的资料",
#     ]
    
#     try:
#         retriever = RAGRetriever(top_k=3)
        
#         for query in test_queries:
#             print(f"\n🔍 查询: {query}")
#             docs = retriever.retrieve(query=query, top_k=3)
            
#             if docs:
#                 print(f"✅ 检索到 {len(docs)} 个文档")
#                 for i, doc in enumerate(docs, 1):
#                     print(f"  [{i}] 相似度: {doc['score']:.3f}")
#                     print(f"      从者: {doc['metadata'].get('servant_name', 'N/A')}")
#                     print(f"      类型: {doc['metadata'].get('chunk_type', 'N/A')}")
#                     print(f"      内容: {doc['content'][:80]}...")
#             else:
#                 print(f"⚠️ 未检索到文档")
        
#         return True
#     except Exception as e:
#         print(f"❌ 基本检索测试失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def test_crossencoder_rerank():
#     """测试 3: CrossEncoder 重排序"""
#     print("\n" + "="*60)
#     print("测试 3: CrossEncoder 重排序")
#     print("="*60)
    
#     query = "玛修的宝具效果是什么"
    
#     try:
#         retriever = RAGRetriever(
#             top_k=5,
#             rerank_model_name="BAAI/bge-reranker-base"
#         )
        
#         print(f"🔍 查询: {query}")
        
#         # 检索并重排序
#         docs = retriever.retrieve_and_rerank(
#             query=query,
#             top_k=5,
#             rerank_method="crossencoder"
#         )
        
#         if docs:
#             print(f"✅ 重排序完成，共 {len(docs)} 个文档")
#             print(f"\n{'排名':<6} {'原始分数':<10} {'CE分数':<10} {'重排分数':<10} {'从者':<15} {'类型'}")
#             print("-" * 80)
            
#             for i, doc in enumerate(docs, 1):
#                 print(
#                     f"{i:<6} "
#                     f"{doc['score']:<10.3f} "
#                     f"{doc.get('ce_score', 0):<10.3f} "
#                     f"{doc.get('rerank_score', 0):<10.3f} "
#                     f"{doc['metadata'].get('servant_name', 'N/A'):<15} "
#                     f"{doc['metadata'].get('chunk_type', 'N/A')}"
#                 )
#                 print(f"       内容: {doc['content'][:100]}...")
#                 print()
#         else:
#             print(f"⚠️ 未检索到文档")
#             return False
        
#         return True
#     except Exception as e:
#         print(f"❌ CrossEncoder 重排序测试失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def test_keyword_rerank():
#     """测试 4: 关键词重排序（fallback）"""
#     print("\n" + "="*60)
#     print("测试 4: 关键词重排序（fallback）")
#     print("="*60)
    
#     query = "玛修的防御技能"
    
#     try:
#         retriever = RAGRetriever(top_k=5)
        
#         print(f"🔍 查询: {query}")
        
#         # 使用关键词重排序
#         docs = retriever.retrieve_and_rerank(
#             query=query,
#             top_k=5,
#             rerank_method="keyword"
#         )
        
#         if docs:
#             print(f"✅ 关键词重排序完成，共 {len(docs)} 个文档")
#             print(f"\n{'排名':<6} {'原始分数':<10} {'重排分数':<10} {'从者':<15} {'类型'}")
#             print("-" * 70)
            
#             for i, doc in enumerate(docs, 1):
#                 print(
#                     f"{i:<6} "
#                     f"{doc['score']:<10.3f} "
#                     f"{doc.get('rerank_score', 0):<10.3f} "
#                     f"{doc['metadata'].get('servant_name', 'N/A'):<15} "
#                     f"{doc['metadata'].get('chunk_type', 'N/A')}"
#                 )
#         else:
#             print(f"⚠️ 未检索到文档")
#             return False
        
#         return True
#     except Exception as e:
#         print(f"❌ 关键词重排序测试失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def test_retrieval_quality():
#     """测试 5: 检索质量评估"""
#     print("\n" + "="*60)
#     print("测试 5: 检索质量评估")
#     print("="*60)
    
#     test_queries = [
#         ("玛修的宝具是什么", "高质量查询"),
#         ("从者", "低质量查询（太宽泛）"),
#         ("阿尔托莉雅·潘德拉贡的誓约胜利之剑", "高质量查询（具体）"),
#     ]
    
#     try:
#         for query, description in test_queries:
#             print(f"\n🔍 查询: {query} ({description})")
            
#             docs = retrieve_documents(
#                 query=query,
#                 top_k=5,
#                 rerank=True,
#                 rerank_method="crossencoder"
#             )
            
#             quality = calculate_retrieval_quality(docs)
            
#             if quality > 0.7:
#                 level = "高质量 ✅"
#             elif quality > 0.5:
#                 level = "中等质量 ⚠️"
#             else:
#                 level = "低质量 ❌"
            
#             print(f"   质量分数: {quality:.3f} ({level})")
#             print(f"   文档数量: {len(docs)}")
#             if docs:
#                 print(f"   Top文档分数: {docs[0].get('rerank_score', 0):.3f}")
        
#         return True
#     except Exception as e:
#         print(f"❌ 质量评估测试失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def test_compare_rerank_methods():
#     """测试 6: 对比不同重排序方法"""
#     print("\n" + "="*60)
#     print("测试 6: 对比不同重排序方法")
#     print("="*60)
    
#     query = "玛修的宝具"
#     methods = ["score", "keyword", "crossencoder"]
    
#     try:
#         retriever = RAGRetriever(top_k=5)
        
#         print(f"🔍 查询: {query}\n")
        
#         results = {}
#         for method in methods:
#             print(f"📊 方法: {method}")
#             docs = retriever.retrieve_and_rerank(
#                 query=query,
#                 top_k=5,
#                 rerank_method=method
#             )
#             results[method] = docs
            
#             if docs:
#                 quality = calculate_retrieval_quality(docs)
#                 print(f"   质量分数: {quality:.3f}")
#                 print(f"   Top文档分数: {docs[0].get('rerank_score', docs[0].get('score')):.3f}")
#                 print(f"   Top文档: {docs[0]['metadata'].get('servant_name')} - {docs[0]['metadata'].get('chunk_type')}")
#             print()
        
#         # 输出对比表格
#         print("\n" + "="*80)
#         print("重排序方法对比（Top 3 文档）")
#         print("="*80)
        
#         for method, docs in results.items():
#             print(f"\n【{method.upper()}】")
#             for i, doc in enumerate(docs[:3], 1):
#                 score = doc.get('rerank_score', doc.get('score', 0))
#                 print(f"  {i}. 分数: {score:.3f} | {doc['metadata'].get('servant_name', 'N/A')} - {doc['metadata'].get('chunk_type', 'N/A')}")
        
#         return True
#     except Exception as e:
#         print(f"❌ 对比测试失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def test_metadata_filter():
#     """测试 7: 元数据过滤"""
#     print("\n" + "="*60)
#     print("测试 7: 元数据过滤")
#     print("="*60)
    
#     query = "宝具效果"
    
#     try:
#         # 测试不带过滤
#         print(f"🔍 查询（无过滤）: {query}")
#         docs_no_filter = retrieve_documents(query=query, top_k=3, rerank=False)
#         print(f"   检索到 {len(docs_no_filter)} 个文档")
#         for doc in docs_no_filter:
#             print(f"   - {doc['metadata'].get('servant_name', 'N/A')}")
        
#         # 测试带过滤（如果知道某个从者名称）
#         if docs_no_filter and docs_no_filter[0]['metadata'].get('servant_name'):
#             servant_name = docs_no_filter[0]['metadata']['servant_name']
#             print(f"\n🔍 查询（过滤从者={servant_name}）: {query}")
#             docs_filtered = retrieve_documents(
#                 query=query,
#                 top_k=3,
#                 rerank=False,
#                 filter_metadata={"servant_name": servant_name}
#             )
#             print(f"   检索到 {len(docs_filtered)} 个文档")
#             for doc in docs_filtered:
#                 print(f"   - {doc['metadata'].get('servant_name', 'N/A')} ({doc['metadata'].get('chunk_type', 'N/A')})")
        
#         return True
#     except Exception as e:
#         print(f"❌ 元数据过滤测试失败: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def run_all_tests():
#     """运行所有测试"""
#     print("\n" + "="*60)
#     print("🚀 开始运行 RAG 模块测试")
#     print("="*60)
    
#     tests = [
#         ("向量数据库连接", test_vectordb_connection),
#         ("基本检索", test_basic_retrieval),
#         ("CrossEncoder重排序", test_crossencoder_rerank),
#         ("关键词重排序", test_keyword_rerank),
#         ("检索质量评估", test_retrieval_quality),
#         ("对比重排序方法", test_compare_rerank_methods),
#         ("元数据过滤", test_metadata_filter),
#     ]
    
#     results = []
#     for test_name, test_func in tests:
#         try:
#             result = test_func()
#             results.append((test_name, result))
#         except Exception as e:
#             print(f"❌ 测试 '{test_name}' 发生异常: {str(e)}")
#             results.append((test_name, False))
    
#     # 输出测试总结
#     print("\n" + "="*60)
#     print("📊 测试总结")
#     print("="*60)
    
#     passed = sum(1 for _, result in results if result)
#     total = len(results)
    
#     for test_name, result in results:
#         status = "✅ 通过" if result else "❌ 失败"
#         print(f"{status} - {test_name}")
    
#     print(f"\n总计: {passed}/{total} 测试通过")
#     print("="*60)
    
#     return passed == total


# if __name__ == "__main__":
#     success = run_all_tests()
#     sys.exit(0 if success else 1)