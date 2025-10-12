import re
from typing import Dict, List, Any
from data.parse.phantasms import parse_noble_phantasms
from data.parse.skills import parse_noble_skills
from data.parse.materials import parse_noble_materials
from data.parse.profile import parse_noble_profiles

def clean_wikitext_value(value: str) -> str:
    """
    清理函数，用于移除常见的Wiki语法标记。
    """
    # 移除链接标记 [[...|显示文本]] -> 显示文本, [[链接]] -> 链接
    value = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', value)
    # 移除 HTML 注释 <!-- ... -->
    value = re.sub(r'<!--[\s\S]*?-->', '', value)
    # 移除 HTML 标签 <...>
    value = re.sub(r'<[^>]+>', ' ', value)
    # 移除斜体/粗体标记 ''', ''
    value = value.replace("'''", "").replace("''", "")
    # 移除模板标记 {{...}}
    value = re.sub(r'\{\{.*?\}\}', '', value)
    # 移除多余的空白
    value = ' '.join(value.split())
    return value.strip()

def parse_key_value_template(template_content: str) -> Dict[str, str]:
    """
    一个通用的函数，用于解析任何 |key=value 格式的模板内容。
    """
    params = {}
    # 参数通常以 '|' 开头，并换行
    lines = template_content.strip().split('\n|')
    
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            params[key.strip()] = value.strip()
    return params

def parse_full_wikitext(wikitext: str) -> Dict[str, Any]:
    """
    主解析函数，只解析指定的五个模块：
    1. 基础数值
    2. 宝具
    3. 技能
    4. 素材需求
    5. 资料
    """
    servant_data = {}

    # 解析基础数值
    base_info_match = re.search(r'\{\{基础数值([\s\S]*?)\}\}', wikitext, re.I)
    if base_info_match:
        content = base_info_match.group(1)
        params = parse_key_value_template(content)
        # 清洗每个值
        cleaned_params = {key: clean_wikitext_value(value) for key, value in params.items()}
        servant_data['基础数值'] = cleaned_params

    section_map = {}
    sections = re.split(r'\n==([^=]+)==\n', wikitext)

    for i in range(1, len(sections), 2):
        title = sections[i].strip()
        content = sections[i+1]
        section_map[title] = content
        # print(title)
        # print('='*100)
    
    # 解析“宝具”模块
    if '宝具' in section_map:
        phantasms = parse_noble_phantasms(section_map['宝具'])
        servant_data['宝具'] = phantasms
    
    # 解析“技能”模块
    if '技能' in section_map:
        
        skills = parse_noble_skills(section_map['技能'])
        servant_data['技能'] = skills
    
    # 解析“素材需求”模块
    if '素材需求' in section_map:
        materials = parse_noble_materials(section_map['素材需求'])
        servant_data['素材需求'] = materials
    
    # 解析“资料”模块
    if '资料' in section_map:
        profiles = parse_noble_profiles(section_map['资料'])
        servant_data['资料'] = profiles

    return servant_data

# if __name__ == '__main__':
#     try:
#         with open('textarea/阿尔托莉雅·潘德拉贡.txt', 'r', encoding='utf-8') as f:
#             wikitext_content = f.read()

#         # with open('textarea/阿育王.txt', 'r', encoding='utf-8') as f:
#         #     wikitext_content = f.read()
            
#         parsed_data = parse_full_wikitext(wikitext_content)
        
#         import json
#         print(json.dumps(parsed_data, indent=2, ensure_ascii=False))

#     except FileNotFoundError:
#         print("路径错误")
#     except Exception as e:
#         print(f"发生错误: {e}")