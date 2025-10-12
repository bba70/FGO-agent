"""
构建 FGO 向量数据库

流程：
1. 读取 textarea 下的所有从者数据
2. 使用 parse_wiki.py 解析
3. 使用 FGOChunker 切分 chunks
4. 存入 ChromaDB
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from data.parse_wiki import parse_full_wikitext
from src.tools.rag.chunker import FGOChunker
from database.kb.vectordb import get_vectordb


def load_all_servants(textarea_dir: Path) -> List[Dict[str, Any]]:
    """
    加载所有从者数据
    
    Args:
        textarea_dir: textarea 目录路径
    
    Returns:
        从者数据列表 [{'name': '...', 'data': {...}}, ...]
    """
    print(f"\n📂 读取从者数据: {textarea_dir}")
    
    servants = []
    txt_files = list(textarea_dir.glob("*.txt"))
    
    if not txt_files:
        print(f"❌ 未找到任何 .txt 文件")
        return servants
    
    print(f"✅ 找到 {len(txt_files)} 个从者文件")
    
    for txt_file in tqdm(txt_files, desc="解析从者数据"):
        try:
            servant_name = txt_file.stem
            
            with open(txt_file, 'r', encoding='utf-8') as f:
                wikitext = f.read()
            
            parsed_data = parse_full_wikitext(wikitext)
            
            if parsed_data:
                servants.append({
                    'name': servant_name,
                    'data': parsed_data
                })
        
        except Exception as e:
            print(f"⚠️  解析 {txt_file.name} 失败: {e}")
            continue
    
    print(f"✅ 成功解析 {len(servants)} 个从者")
    return servants


def chunk_servants(servants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    切分从者数据
    
    Args:
        servants: 从者数据列表
    
    Returns:
        chunks 列表
    """
    print(f"\n✂️  切分数据块...")
    chunker = FGOChunker()
    all_chunks = []
    
    for servant in tqdm(servants, desc="切分数据"):
        chunks = chunker.chunk_servant(servant['name'], servant['data'])
        all_chunks.extend(chunks)
    
    print(f"✅ 共切分出 {len(all_chunks)} 个数据块")
    
    # 显示统计
    stats = chunker.get_stats(all_chunks)
    print(f"\n📊 切块统计：")
    print(f"   总块数: {stats['total_chunks']}")
    print(f"   从者数: {stats['total_servants']}")
    print(f"   平均长度: {stats['avg_chunk_length']} 字符")
    print(f"   按类型分布:")
    for type_name, count in stats['chunks_by_type'].items():
        print(f"     {type_name}: {count} 个")
    
    # 显示样例
    if all_chunks:
        print(f"\n📄 数据块示例：")
        sample = all_chunks[0]
        print(f"   ID: {sample['id']}")
        print(f"   元数据: {sample['metadata']}")
        print(f"   内容预览: {sample['content'][:150]}...")
    
    return all_chunks


def insert_to_vectordb(chunks: List[Dict[str, Any]]):
    """
    插入数据到向量数据库
    
    Args:
        chunks: 文档块列表
    """
    print(f"\n📦 初始化向量数据库...")
    vectordb = get_vectordb()
    collection = vectordb.get_or_create_collection()
    
    # 检查是否已有数据
    existing_count = collection.count()
    if existing_count > 0:
        print(f"⚠️  集合中已有 {existing_count} 条数据")
        response = input("是否清空现有数据？(y/n): ")
        if response.lower() == 'y':
            print("🗑️  清空现有数据...")
            vectordb.delete_collection(collection.name)
            collection = vectordb.get_or_create_collection()
        else:
            print("⚠️  保留现有数据，新数据将追加")
    
    # 批量插入
    print(f"\n📝 插入数据到向量数据库...")
    batch_size = 10  # 每批次插入 10 条（Qwen Embedding API 限制）
    
    for i in tqdm(range(0, len(chunks), batch_size), desc="插入数据"):
        batch = chunks[i:i+batch_size]
        
        try:
            collection.add(
                documents=[chunk['content'] for chunk in batch],
                metadatas=[chunk['metadata'] for chunk in batch],
                ids=[chunk['id'] for chunk in batch]
            )
        except Exception as e:
            print(f"\n❌ 批次 {i//batch_size + 1} 插入失败: {e}")
            # 继续下一批
            continue
    
    print(f"✅ 数据插入完成！")
    print(f"   总文档数: {collection.count()}")
    
    return collection


def test_retrieval(collection):
    """
    测试检索功能
    
    Args:
        collection: ChromaDB 集合
    """
    print(f"\n🔍 测试检索功能...")
    
    test_queries = [
        "阿尔托莉雅的基础数值",
        "梅林的技能",
        "吉尔伽美什的宝具",
        "赫拉克勒斯的素材需求"
    ]
    
    for query in test_queries:
        print(f"\n   查询: {query}")
        try:
            results = collection.query(
                query_texts=[query],
                n_results=3
            )
            
            if results and results['ids'] and results['ids'][0]:
                for j, (doc_id, distance) in enumerate(zip(results['ids'][0], results['distances'][0]), 1):
                    # ChromaDB 返回距离（越小越相似），转换为相似度
                    similarity = 1 / (1 + distance)
                    print(f"     {j}. ID: {doc_id}, 相似度: {similarity:.3f}")
            else:
                print("     未找到结果")
        except Exception as e:
            print(f"     ❌ 查询失败: {e}")


def build_vectorstore():
    """主函数：构建向量数据库"""
    print("\n" + "=" * 80)
    print("🚀 开始构建 FGO 向量数据库")
    print("=" * 80)
    
    try:
        # 1. 加载从者数据
        textarea_dir = project_root / "data" / "textarea"
        servants = load_all_servants(textarea_dir)
        
        if not servants:
            print("❌ 没有找到任何从者数据!")
            return
        
        # 2. 切分数据
        chunks = chunk_servants(servants)
        
        if not chunks:
            print("❌ 没有切分出任何数据块!")
            return
        
        # 3. 存入向量数据库
        collection = insert_to_vectordb(chunks)
        
        # 4. 测试检索
        test_retrieval(collection)
        
        # 5. 完成
        vectordb = get_vectordb()
        print("\n" + "=" * 80)
        print("✅ 向量数据库构建完成！")
        print("=" * 80)
        print(f"   存储路径: {vectordb.config.persist_directory}")
        print(f"   集合名称: {vectordb.config.collection_name}")
        print(f"   文档总数: {collection.count()}")
        print(f"   Embedding模型: {vectordb.config.embedding_model_name}")
        print("=" * 80)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
    except Exception as e:
        print(f"\n\n❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    build_vectorstore()

