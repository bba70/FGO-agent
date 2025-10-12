"""
FGO 数据切块器

将解析后的从者数据按照规则切分成适合向量检索的文档块

切分规则：
1. 基础数值 - 一整块
2. 宝具 - 每个宝具一块
3. 技能 - 每个技能一块
4. 素材需求 - 一整块
5. 资料 - 按资料1、资料2等切分
"""

from typing import List, Dict, Any


class FGOChunker:
    """FGO 数据切块器"""
    
    def chunk_servant(self, servant_name: str, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        切分单个从者的数据
        
        Args:
            servant_name: 从者名称（文件名）
            parsed_data: parse_full_wikitext 的输出
        
        Returns:
            chunks 列表，每个 chunk 包含 {content, metadata, id}
        """
        chunks = []
        
        # 1. 基础数值（一整块）
        if '基础数值' in parsed_data:
            chunk = self._chunk_base_info(servant_name, parsed_data['基础数值'])
            if chunk:
                chunks.append(chunk)
        
        # 2. 宝具（每个一块）
        if '宝具' in parsed_data:
            chunks.extend(self._chunk_phantasms(servant_name, parsed_data['宝具']))
        
        # 3. 技能（每个一块）
        if '技能' in parsed_data:
            chunks.extend(self._chunk_skills(servant_name, parsed_data['技能']))
        
        # 4. 素材需求（一整块）
        if '素材需求' in parsed_data:
            chunk = self._chunk_materials(servant_name, parsed_data['素材需求'])
            if chunk:
                chunks.append(chunk)
        
        # 5. 资料（按资料1、资料2切分）
        if '资料' in parsed_data:
            chunks.extend(self._chunk_profiles(servant_name, parsed_data['资料']))
        
        return chunks
    
    def _chunk_base_info(self, servant_name: str, base_info: Dict[str, str]) -> Dict[str, Any]:
        """切分基础数值（一整块）"""
        # 语义化前缀：让 embedding 更容易理解这是关于从者的基础信息
        lines = [f"{servant_name}是一位从者，其基础数值和属性如下：", ""]
        
        for key, value in base_info.items():
            if value and str(value).strip():
                lines.append(f"{key}：{value}")
        
        return {
            'content': "\n".join(lines),
            'metadata': {
                'servant_name': servant_name,
                'type': '基础数值',
            },
            'id': f'{servant_name}_基础数值'
        }
    
    def _chunk_phantasms(self, servant_name: str, phantasms: List[Dict]) -> List[Dict[str, Any]]:
        """切分宝具（每个宝具一块）"""
        chunks = []
        for i, phantasm in enumerate(phantasms, 1):
            # 提取宝具名称用于语义化前缀
            phantasm_name = phantasm.get('宝具名', phantasm.get('宝具名称', f'宝具{i}'))
            
            # 语义化前缀：自然语言描述
            if phantasm_name and phantasm_name != f'宝具{i}':
                lines = [f"{servant_name}的宝具是「{phantasm_name}」，详细信息如下：", ""]
            else:
                lines = [f"{servant_name}的第{i}个宝具，详细信息如下：", ""]
            
            for key, value in phantasm.items():
                if not value:
                    continue
                if isinstance(value, dict):
                    lines.append(f"{key}：")
                    for k, v in value.items():
                        lines.append(f"  {k}：{v}")
                elif isinstance(value, list):
                    lines.append(f"{key}：{', '.join(str(v) for v in value)}")
                else:
                    lines.append(f"{key}：{value}")
            
            chunks.append({
                'content': "\n".join(lines),
                'metadata': {
                    'servant_name': servant_name,
                    'type': '宝具',
                    'phantasm_name': phantasm_name,
                    'index': i,
                },
                'id': f'{servant_name}_宝具{i}'
            })
        
        return chunks
    
    def _chunk_skills(self, servant_name: str, skills: List[Dict]) -> List[Dict[str, Any]]:
        """切分技能（每个技能一块）
        
        skills 格式：[
            {'持有技能1': {...}},
            {'持有技能2': {...}},
            {'职阶技能1': {...}, '职阶技能2': {...}}
        ]
        """
        chunks = []
        
        # 用于跟踪每个技能名称的出现次数，处理强化前/后的重复技能
        skill_name_counter = {}
        
        # skills 是一个列表，每个元素是一个字典
        for skill_dict in skills:
            for skill_name, skill_data in skill_dict.items():
                # 提取技能名称用于语义化前缀
                actual_skill_name = skill_data.get('技能名', skill_data.get('技能名称', skill_name))
                
                # 判断是否是强化技能
                is_enhanced = skill_data.get('是否强化', '')
                enhanced_text = f"（{is_enhanced}）" if is_enhanced and '强化' in str(is_enhanced) else ""
                
                # 语义化前缀：自然语言描述
                if actual_skill_name and actual_skill_name != skill_name:
                    lines = [f"{servant_name}的{skill_name}是「{actual_skill_name}」{enhanced_text}，详细信息如下：", ""]
                else:
                    lines = [f"{servant_name}的{skill_name}{enhanced_text}，详细信息如下：", ""]
                
                for key, value in skill_data.items():
                    if not value or key == '是否强化':  # 跳过空值和已处理的字段
                        continue
                    if isinstance(value, dict):
                        lines.append(f"{key}：")
                        for k, v in value.items():
                            lines.append(f"  {k}：{v}")
                    elif isinstance(value, list):
                        lines.append(f"{key}：{', '.join(str(v) for v in value)}")
                    else:
                        lines.append(f"{key}：{value}")
                
                # 生成唯一ID：如果技能名重复，添加序号后缀
                if skill_name in skill_name_counter:
                    skill_name_counter[skill_name] += 1
                    unique_id = f'{servant_name}_{skill_name}_v{skill_name_counter[skill_name]}'
                else:
                    skill_name_counter[skill_name] = 1
                    unique_id = f'{servant_name}_{skill_name}'
                
                chunks.append({
                    'content': "\n".join(lines),
                    'metadata': {
                        'servant_name': servant_name,
                        'type': '技能',
                        'skill_name': skill_name,
                        'actual_skill_name': actual_skill_name,
                        'is_enhanced': bool(is_enhanced and '强化' in str(is_enhanced)),
                        'version': skill_name_counter[skill_name],
                    },
                    'id': unique_id
                })
        
        return chunks
    
    def _chunk_materials(self, servant_name: str, materials: List[Dict]) -> Dict[str, Any]:
        """切分素材需求（一整块）
        
        materials 格式：[
            {'灵基再临（从者进化）': {...}},
            {'技能强化': {...}},
            ...
        ]
        """
        # 语义化前缀
        lines = [f"{servant_name}的培养所需素材如下：", ""]
        
        # materials 是一个列表，每个元素是一个字典
        for material_dict in materials:
            for category, items in material_dict.items():
                lines.append(f"【{category}】")
                if isinstance(items, dict):
                    for k, v in items.items():
                        if v:  # 只添加非空值
                            lines.append(f"{k}：{v}")
                elif isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                if v:
                                    lines.append(f"{k}：{v}")
                        else:
                            lines.append(str(item))
                else:
                    lines.append(str(items))
                lines.append("")
        
        return {
            'content': "\n".join(lines),
            'metadata': {
                'servant_name': servant_name,
                'type': '素材需求',
            },
            'id': f'{servant_name}_素材需求'
        }
    
    def _chunk_profiles(self, servant_name: str, profiles: List[Dict]) -> List[Dict[str, Any]]:
        """切分资料（按资料1、资料2等）
        
        profiles 格式：[
            {'type': '详情', 'content': '...', 'condition': '...'},
            {'type': '资料1', 'content': '...', 'condition': '...'},
            ...
        ]
        """
        chunks = []
        
        # profiles 是一个列表，每个元素是一个包含 type, content, condition 的字典
        for profile_data in profiles:
            profile_type = profile_data.get('type', '未知资料')
            content = profile_data.get('content', '')
            condition = profile_data.get('condition', '')
            
            if not content:  # 跳过空内容
                continue
            
            # 语义化前缀
            lines = [f"{servant_name}的{profile_type}：", ""]
            
            if condition:
                lines.append(f"（开放条件：{condition}）")
                lines.append("")
            
            lines.append(content)
            
            chunks.append({
                'content': "\n".join(lines),
                'metadata': {
                    'servant_name': servant_name,
                    'type': '资料',
                    'profile_type': profile_type,
                    'condition': condition,
                },
                'id': f'{servant_name}_{profile_type}'
            })
        
        return chunks
    
    def get_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取切块统计信息
        
        Args:
            chunks: 文档块列表
        
        Returns:
            统计信息字典
        """
        from collections import Counter
        
        # 按类型统计
        type_counter = Counter(chunk['metadata'].get('type', 'Unknown') for chunk in chunks)
        
        # 按从者统计
        servant_counter = Counter(chunk['metadata'].get('servant_name', 'Unknown') for chunk in chunks)
        
        # 内容长度统计
        lengths = [len(chunk['content']) for chunk in chunks]
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        
        return {
            'total_chunks': len(chunks),
            'chunks_by_type': dict(type_counter),
            'total_servants': len(servant_counter),
            'avg_chunk_length': int(avg_length),
            'min_chunk_length': min(lengths) if lengths else 0,
            'max_chunk_length': max(lengths) if lengths else 0
        }

