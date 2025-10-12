"""
测试 parse.py 的输出结构
"""


import json
from data.parse import parse_full_wikitext

# 读取一个示例文件
with open('textarea/阿尔托莉雅·潘德拉贡.txt', 'r', encoding='utf-8') as f:
    wikitext_content = f.read()

# 解析
parsed_data = parse_full_wikitext(wikitext_content)

# 打印JSON结构
print(json.dumps(parsed_data, indent=2, ensure_ascii=False))

# 打印结构概览
print("\n" + "="*80)
print("数据结构概览：")
print("="*80)
for key, value in parsed_data.items():
    if isinstance(value, dict):
        print(f"\n【{key}】 (字典)")
        for k, v in list(value.items())[:3]:  # 只显示前3个
            print(f"  {k}: {str(v)[:50]}...")
    elif isinstance(value, list):
        print(f"\n【{key}】 (列表, 长度: {len(value)})")
        if value:
            print(f"  第一项类型: {type(value[0])}")
            if isinstance(value[0], dict):
                print(f"  第一项的键: {list(value[0].keys())}")
    else:
        print(f"\n【{key}】: {str(value)[:50]}")