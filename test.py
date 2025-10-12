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



"""
测试向量数据库连接

测试内容：
1. 配置加载
2. 连接初始化
3. Embedding 函数
4. 集合创建
5. 数据插入和查询
"""

import asyncio

from database.kb.config import get_vectordb_config, update_config
from database.kb.connection import get_vectordb_connection, reset_connection


def test_config():
    """测试1：配置加载"""
    print("\n" + "=" * 80)
    print("测试 1: 配置加载")
    print("=" * 80)
    
    try:
        config = get_vectordb_config()
        
        print(f"✅ 配置加载成功")
        print(f"   向量数据库路径: {config.persist_directory}")
        print(f"   集合名称: {config.collection_name}")
        print(f"   LLM 配置路径: {config.llm_config_path}")
        print(f"   Embedding 模型: {config.embedding_model_name}")
        print(f"   默认检索数量 k: {config.default_k}")
        
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


def test_connection_init():
    """测试2：连接初始化"""
    print("\n" + "=" * 80)
    print("测试 2: 连接初始化")
    print("=" * 80)
    
    try:
        connection = get_vectordb_connection()
        
        print(f"✅ 连接对象创建成功")
        print(f"   类型: {type(connection)}")
        
        # 测试获取客户端
        client = connection.get_client()
        print(f"✅ ChromaDB 客户端初始化成功")
        print(f"   类型: {type(client)}")
        
        # 列出现有集合
        collections = connection.list_collections()
        print(f"✅ 现有集合数量: {len(collections)}")
        if collections:
            print(f"   集合列表: {collections}")
        
        return True
    except Exception as e:
        print(f"❌ 连接初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_embedding_function():
    """测试3：Embedding 函数"""
    print("\n" + "=" * 80)
    print("测试 3: Embedding 函数")
    print("=" * 80)
    
    try:
        connection = get_vectordb_connection()
        
        # 获取 Embedding 函数
        print("📦 正在初始化 Embedding 函数...")
        embedding_func = connection.get_embedding_function()
        
        print(f"✅ Embedding 函数创建成功")
        print(f"   类型: {type(embedding_func)}")
        
        # 测试编码
        print("\n📝 测试文本编码...")
        test_texts = [
            "阿尔托莉雅·潘德拉贡是一位Saber职阶的从者",
            "梅林是强力的辅助型Caster"
        ]
        
        print(f"   输入文本数量: {len(test_texts)}")
        for i, text in enumerate(test_texts, 1):
            print(f"   文本{i}: {text[:30]}...")
        
        print("\n🔄 正在调用 LLM Router 生成向量...")
        vectors = embedding_func(test_texts)
        
        print(f"✅ 向量生成成功!")
        print(f"   返回向量数量: {len(vectors)}")
        print(f"   向量维度: {len(vectors[0]) if vectors else 0}")
        print(f"   第一个向量前5维: {vectors[0][:5] if vectors else []}")
        
        return True
    except Exception as e:
        print(f"❌ Embedding 函数测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_collection_operations():
    """测试4：集合操作"""
    print("\n" + "=" * 80)
    print("测试 4: 集合操作")
    print("=" * 80)
    
    try:
        connection = get_vectordb_connection()
        
        # 创建测试集合
        test_collection_name = "test_collection"
        
        print(f"📦 创建测试集合: {test_collection_name}")
        collection = connection.get_or_create_collection(
            collection_name=test_collection_name,
            metadata={"description": "测试集合"}
        )
        
        print(f"✅ 集合创建成功")
        print(f"   集合名称: {collection.name}")
        print(f"   文档数量: {collection.count()}")
        
        # 插入测试数据
        print("\n📝 插入测试数据...")
        test_documents = [
            "从者：阿尔托莉雅·潘德拉贡\n类型：基础数值\n职阶：Saber",
            "从者：梅林\n类型：主动技能1\n技能名：梦幻的魅惑 A"
        ]
        test_ids = ["test_doc_1", "test_doc_2"]
        test_metadatas = [
            {"servant_name": "阿尔托莉雅", "type": "基础数值"},
            {"servant_name": "梅林", "type": "技能"}
        ]
        
        collection.add(
            documents=test_documents,
            ids=test_ids,
            metadatas=test_metadatas
        )
        
        print(f"✅ 数据插入成功")
        print(f"   插入文档数: {len(test_documents)}")
        print(f"   当前总文档数: {collection.count()}")
        
        # 查询数据
        print("\n🔍 测试查询功能...")
        query_text = "阿尔托莉雅的基础数值"
        
        print(f"   查询文本: {query_text}")
        results = collection.query(
            query_texts=[query_text],
            n_results=2
        )
        
        print(f"✅ 查询成功")
        print(f"   返回结果数: {len(results['ids'][0])}")
        for i, (doc_id, document, distance) in enumerate(zip(
            results['ids'][0],
            results['documents'][0],
            results['distances'][0]
        ), 1):
            print(f"\n   结果{i}:")
            print(f"     ID: {doc_id}")
            print(f"     距离: {distance:.4f}")
            print(f"     文档: {document[:50]}...")
        
        # 清理测试集合
        print(f"\n🗑️  清理测试集合...")
        connection.delete_collection(test_collection_name)
        print(f"✅ 测试集合已删除")
        
        return True
    except Exception as e:
        print(f"❌ 集合操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_workflow():
    """测试5：完整工作流"""
    print("\n" + "=" * 80)
    print("测试 5: 完整工作流（插入 → 检索 → 过滤）")
    print("=" * 80)
    
    try:
        connection = get_vectordb_connection()
        
        # 创建测试集合
        test_collection_name = "test_full_workflow"
        collection = connection.get_or_create_collection(test_collection_name)
        
        # 插入多个从者数据
        print("📝 插入测试数据...")
        documents = [
            "从者：阿尔托莉雅\n类型：宝具1\n宝具名：誓约胜利之剑\n卡色：Buster",
            "从者：阿尔托莉雅\n类型：主动技能1\n技能名：直感 A\n效果：自身获得星星",
            "从者：梅林\n类型：宝具1\n宝具名：永久遥远的理想乡\n卡色：Arts",
            "从者：梅林\n类型：主动技能1\n技能名：梦幻的魅惑 A\n效果：自身NP获得",
            "从者：吉尔伽美什\n类型：宝具1\n宝具名：天地乖离开辟之星\n卡色：Buster"
        ]
        ids = [f"doc_{i}" for i in range(1, 6)]
        metadatas = [
            {"servant_name": "阿尔托莉雅", "type": "宝具"},
            {"servant_name": "阿尔托莉雅", "type": "技能"},
            {"servant_name": "梅林", "type": "宝具"},
            {"servant_name": "梅林", "type": "技能"},
            {"servant_name": "吉尔伽美什", "type": "宝具"}
        ]
        
        collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas
        )
        print(f"✅ 插入 {len(documents)} 条数据")
        
        # 测试1：纯向量搜索
        print("\n🔍 测试1: 纯向量搜索")
        print("   查询: 'Buster宝具'")
        results = collection.query(
            query_texts=["Buster宝具"],
            n_results=3
        )
        print(f"   返回 {len(results['ids'][0])} 个结果:")
        for doc_id, meta in zip(results['ids'][0], results['metadatas'][0]):
            print(f"     {doc_id}: {meta['servant_name']} - {meta['type']}")
        
        # 测试2：带元数据过滤的搜索
        print("\n🔍 测试2: 元数据过滤搜索")
        print("   查询: 'Buster宝具' + where={'servant_name': '阿尔托莉雅'}")
        results = collection.query(
            query_texts=["Buster宝具"],
            where={"servant_name": "阿尔托莉雅"},
            n_results=3
        )
        print(f"   返回 {len(results['ids'][0])} 个结果:")
        for doc_id, meta in zip(results['ids'][0], results['metadatas'][0]):
            print(f"     {doc_id}: {meta['servant_name']} - {meta['type']}")
        
        # 测试3：精确ID查询
        print("\n🔍 测试3: 精确ID查询")
        print("   查询ID: ['doc_1', 'doc_3']")
        results = collection.get(
            ids=["doc_1", "doc_3"],
            include=["documents", "metadatas"]
        )
        print(f"   返回 {len(results['ids'])} 个结果:")
        for doc_id, meta in zip(results['ids'], results['metadatas']):
            print(f"     {doc_id}: {meta['servant_name']} - {meta['type']}")
        
        # 清理
        print(f"\n🗑️  清理测试数据...")
        connection.delete_collection(test_collection_name)
        
        return True
    except Exception as e:
        print(f"❌ 完整工作流测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "🚀" * 40)
    print(" " * 20 + "向量数据库连接测试")
    print("🚀" * 40)
    
    results = []
    
    # 运行测试
    results.append(("配置加载", test_config()))
    results.append(("连接初始化", test_connection_init()))
    results.append(("Embedding函数", test_embedding_function()))
    results.append(("集合操作", test_collection_operations()))
    results.append(("完整工作流", test_full_workflow()))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}  {test_name}")
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！向量数据库连接正常！")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查配置和环境")
    
    # 清理连接
    print("\n🔒 清理连接...")
    reset_connection()
    print("✅ 连接已清理")


if __name__ == "__main__":
    main()