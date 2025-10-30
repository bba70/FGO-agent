"""
查询增强工具
提取从者名称并优化查询，提高检索精度
"""

import json
from pathlib import Path
from typing import List, Tuple, Optional


class QueryEnhancer:
    """查询增强器 - 提取从者名称并扩展查询"""
    
    def __init__(self):
        """加载从者别名映射"""
        # 加载 servant_aliases.json
        project_root = Path(__file__).parent.parent.parent.parent
        aliases_file = project_root / "data" / "servant_aliases.json"
        
        self.servant_aliases = {}
        if aliases_file.exists():
            with open(aliases_file, 'r', encoding='utf-8') as f:
                self.servant_aliases = json.load(f)
        
        # 构建反向索引：别名 -> 标准名
        self.alias_to_standard = {}
        for standard_name, aliases in self.servant_aliases.items():
            self.alias_to_standard[standard_name] = standard_name
            for alias in aliases:
                self.alias_to_standard[alias] = standard_name
    
    def extract_servant_name(self, query: str) -> Optional[str]:
        """
        从查询中提取从者名称
        
        Args:
            query: 用户查询
            
        Returns:
            标准从者名称（如果找到）
        """
        # 按别名长度排序（长的优先匹配，避免部分匹配）
        sorted_aliases = sorted(self.alias_to_standard.keys(), key=len, reverse=True)
        
        for alias in sorted_aliases:
            if alias in query:
                standard_name = self.alias_to_standard[alias]
                return standard_name
        
        return None
    
    def enhance_query(self, query: str) -> Tuple[str, Optional[str]]:
        """
        增强查询：提取从者名称并扩展查询
        
        Args:
            query: 原始查询
            
        Returns:
            (增强后的查询, 提取的从者名称)
        """
        servant_name = self.extract_servant_name(query)
        
        if servant_name:
            # 🎯 策略：在查询中重复从者名称，增强权重
            # 例如："玛修的素材" -> "玛修·基列莱特的素材。玛修·基列莱特需要什么材料"
            enhanced_query = f"{servant_name}。{query}。{servant_name}"
            return enhanced_query, servant_name
        
        return query, None
    
    def get_all_servant_names(self) -> List[str]:
        """获取所有标准从者名称"""
        return list(self.servant_aliases.keys())


# 全局单例
_query_enhancer = None

def get_query_enhancer() -> QueryEnhancer:
    """获取 QueryEnhancer 单例"""
    global _query_enhancer
    if _query_enhancer is None:
        _query_enhancer = QueryEnhancer()
    return _query_enhancer

