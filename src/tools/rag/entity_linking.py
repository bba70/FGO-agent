"""
实体链接模块
将查询中的从者别名/简称映射为标准全名
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class EntityLinker:
    """从者实体链接器"""
    
    def __init__(self, mapping_file: Optional[str] = None):
        """
        初始化实体链接器
        
        Args:
            mapping_file: 映射文件路径（JSON格式）
                         如果不提供，使用默认路径
        """
        if mapping_file is None:
            # 默认路径：data/servant_aliases.json
            # __file__ = FGO-agent/src/tools/rag/entity_linking.py
            # parent x4 = FGO-agent/
            mapping_file = Path(__file__).parent.parent.parent.parent / "data" / "servant_aliases.json"
        
        self.mapping_file = Path(mapping_file)
        self.alias_to_canonical = {}  # 别名 → 标准名
        self.canonical_to_aliases = {}  # 标准名 → 别名列表
        
        self._load_mapping()
    
    def _load_mapping(self):
        """加载映射表"""
        try:
            if not self.mapping_file.exists():
                logger.warning(f"映射文件不存在: {self.mapping_file}")
                logger.warning("实体链接将不生效，请创建映射文件")
                return

            print('路径为', self.mapping_file)
            
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 构建双向映射
            for canonical_name, aliases in data.items():
                # 标准名 → 别名列表
                self.canonical_to_aliases[canonical_name] = aliases
                
                # 别名 → 标准名
                for alias in aliases:
                    self.alias_to_canonical[alias.lower()] = canonical_name
                
                # 标准名自己也映射到自己
                self.alias_to_canonical[canonical_name.lower()] = canonical_name
            
            logger.info(f"✅ 加载实体映射: {len(self.canonical_to_aliases)} 个从者, {len(self.alias_to_canonical)} 个别名")
            
        except Exception as e:
            logger.error(f"❌ 加载实体映射失败: {e}")
    
    def link(self, query: str) -> str:
        """
        对查询进行实体链接
        
        Args:
            query: 原始查询
            
        Returns:
            链接后的查询（别名替换为标准名）
        
        Examples:
            >>> linker = EntityLinker()
            >>> linker.link("Saber的宝具是什么")
            "阿尔托莉雅·潘德拉贡的宝具是什么"
            >>> linker.link("小莫的技能")
            "莫德雷德的技能"
        """
        if not self.alias_to_canonical:
            return query  # 没有映射表，直接返回
        
        linked_query = query
        
        # 按照别名长度从长到短排序（避免短别名误匹配）
        sorted_aliases = sorted(
            self.alias_to_canonical.keys(),
            key=len,
            reverse=True
        )
        
        # 逐个替换别名
        for alias in sorted_aliases:
            # 大小写不敏感匹配
            if alias in linked_query.lower():
                canonical = self.alias_to_canonical[alias]
                
                # 找到原始查询中的实际大小写
                # 简单实现：直接替换（可以优化为保留上下文的替换）
                import re
                pattern = re.compile(re.escape(alias), re.IGNORECASE)
                linked_query = pattern.sub(canonical, linked_query)
                
                logger.debug(f"实体链接: '{alias}' → '{canonical}'")
                break  # 只替换第一个匹配的（避免过度替换）
        
        return linked_query
    
    def get_canonical_name(self, alias: str) -> Optional[str]:
        """
        获取别名对应的标准名
        
        Args:
            alias: 别名
            
        Returns:
            标准名，如果找不到返回 None
        """
        return self.alias_to_canonical.get(alias.lower())
    
    def get_aliases(self, canonical_name: str) -> List[str]:
        """
        获取标准名的所有别名
        
        Args:
            canonical_name: 标准名
            
        Returns:
            别名列表
        """
        return self.canonical_to_aliases.get(canonical_name, [])
    
    def add_alias(self, canonical_name: str, alias: str):
        """
        动态添加别名（运行时）
        
        Args:
            canonical_name: 标准名
            alias: 新别名
        """
        self.alias_to_canonical[alias.lower()] = canonical_name
        
        if canonical_name not in self.canonical_to_aliases:
            self.canonical_to_aliases[canonical_name] = []
        
        if alias not in self.canonical_to_aliases[canonical_name]:
            self.canonical_to_aliases[canonical_name].append(alias)
        
        logger.info(f"添加别名: '{alias}' → '{canonical_name}'")


# 全局单例
_global_linker: Optional[EntityLinker] = None


def get_entity_linker() -> EntityLinker:
    """获取全局实体链接器（单例模式）"""
    global _global_linker
    if _global_linker is None:
        _global_linker = EntityLinker()
    return _global_linker


def link_entities(query: str) -> str:
    """
    便捷函数：对查询进行实体链接
    
    Args:
        query: 原始查询
        
    Returns:
        链接后的查询
    """
    linker = get_entity_linker()
    return linker.link(query)


# ==================== 测试代码 ====================

def test_entity_linking():
    """测试实体链接功能"""
    print("\n" + "="*60)
    print("实体链接测试")
    print("="*60)
    
    linker = EntityLinker()
    
    test_cases = [
        "Saber的宝具是什么",
        "小莫的技能效果",
        "闪闪厉害吗",
        "呆毛王和黑呆的区别",
        "阿尔托莉雅·潘德拉贡的资料",  # 标准名，不应改变
        "她的宝具",  # 没有别名，不应改变
    ]
    
    for query in test_cases:
        linked = linker.link(query)
        if linked != query:
            print(f"✅ '{query}' → '{linked}'")
        else:
            print(f"⚪ '{query}' （无变化）")
    
    print("="*60)


if __name__ == "__main__":
    test_entity_linking()

