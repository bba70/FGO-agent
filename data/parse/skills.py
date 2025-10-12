import re
from typing import Dict, List, Any

def parse_skill_block(skill_block: str) -> Dict:
    '''解析一个技能块'''

    data ={}
    start_index = skill_block.find("{{")
    prefix = skill_block[:start_index]
    if not prefix.strip():
        data['是否强化'] = '该技能未经过强化'
    else:
        data['是否强化'] = prefix.strip()
    
    raws = skill_block[start_index:].strip('}}').split('\n')
    base_info = raws[0].strip().split('|')
    data['技能类型'] = base_info[1].strip()
    data['中文名'] = base_info[2].strip()
    data['日文名'] = base_info[3].strip()
    cd = int(base_info[4].strip())
    data['冷却时间'] = f"初始冷却为{cd}回合， 技能等级为6冷却时间为{cd - 1}回合，技能等级为10冷却时间为{cd - 2}回合"
    # print('raws', raws)

    # 早期与现在的数据格式不统一
    if raws[1].count('|') <= 2:
        idx = 0
        for i in range(1, len(raws), 2):
            effect = raws[i].strip()
            if not effect.strip():
                continue
            nums = raws[i + 1].strip().split('|')
            num_values = [item for item in nums if item not in ('')]
            if len(num_values) == 1:
                data[f"效果{chr(idx + ord('A'))}"] = f"{effect}，不受等级影响"
            else:
                data[f"效果{chr(idx + ord('A'))}"] = effect
                for j, num in enumerate(num_values):
                    data[f"效果{chr(idx + ord('A'))}{str(j + 1)}"] = f"{effect}，等级{j + 1}时数值为{num}"

            idx += 1
    else:
        idx = 0
        for i in range(1, len(raws)):
            effect_value = raws[i].strip().split('|')
            effect_value_cleaned = [item for item in effect_value if item not in ('')]
            if len(effect_value_cleaned) <= 1:
                continue
            effect = effect_value_cleaned[0]
            nums = effect_value_cleaned[1:]
            if len(nums) == 1:
                data[f"效果{chr(idx + ord('A'))}"] = f"{effect}，不受等级影响"
            else:
                data[f"效果{chr(idx + ord('A'))}"] = effect
                for j, num in enumerate(nums):
                    data[f"效果{chr(idx + ord('A'))}{str(j + 1)}"] = f"{effect}，等级{j + 1}时数值为{num}"
            idx += 1
    # print(data)
    return data
        

def parse_skills(text_block, type):
    """
    解析 FGO 技能数据块，处理持有技能、职阶技能和强化/弱化标签。
    
    参数:
    full_text (str): 包含所有技能信息的完整文本块。
    type (str): 技能类型，例如 '持有技能' 或 '职阶技能'
    
    返回:
    dict: 结构化的技能数据。
    """
    

    result = []

    if type == '持有技能':
        
        skill_blocks = re.split(r"('''.*?''')", text_block, flags=re.DOTALL)
        for i in range(1, len(skill_blocks), 2):
            data = {}
            skill_title = skill_blocks[i].strip().replace("'''", "") # 清理标题，例如 '技能1（初期开放）'
            content = skill_blocks[i+1].strip()
            if '<tabber>' in content:
                content_inside_tabber = re.search(r'<tabber>([\s\S]*?)</tabber>', content, re.I).group(1)
                # 使用 '|-|' 作为分隔符，分割出不同的版本块
                version_blocks = content_inside_tabber.split('|-|')
                for block in version_blocks:
                    parsed_content = parse_skill_block(block)
                    result.append({
                        f"{type}{i //2 + 1}": parsed_content
                    })
            else:
                parsed_content = parse_skill_block(content)
                result.append({
                    f"{type}{i //2 + 1}": parsed_content
                })

    else:
        clead_text = text_block.split('\n')
        idx = 0
        data = {}
        # print(222)
        for block in clead_text:
            if not block.strip() or '}}' in block:
                continue
            # print('block', block)
            values = block.split('|')
            value_cleaned = [item for item in values if item not in ('')]
            data[f"{type}{idx + 1}"] = {
                '中文名': value_cleaned[2] + value_cleaned[3],
                '效果和数值': value_cleaned[4],
            }
            idx += 1
        result.append(data)

    # print(999)

    return result
            


                
def parse_noble_skills(np_section_text: str) -> List[Dict[str, str]]:
    """技能解析器"""
    result = []
    # print(777)
    blocks = re.split(r'===(.*?)\s*===', np_section_text, flags=re.DOTALL)
    # print('blocks', blocks)
    for i in range(1, len(blocks), 2):
        title = blocks[i].strip()
        content = blocks[i+1]
        # content = ''
        # print(title)
        # print(content)
        # print('=='*20)
        if '持有技能' in title:
            parsed_np = parse_skills(content, '持有技能')
            result.extend(parsed_np)
        elif '职阶技能' in title:
            parsed_np = parse_skills(content, '职阶技能')
            result.extend(parsed_np)

    return result

# --- 格式化函数 (可选，用于清晰展示) ---
def format_fgo_skills(data):
    output = ["--- 角色技能分析 ---"]
    
    # 1. 持有技能
    output.append("\n## 持有技能 (Active Skills)")
    for skill_key, skill_data in data['持有技能'].items():
        if not skill_data: continue
        
        output.append(f"\n- **{skill_key}** ({skill_data['中文名']} / {skill_data['日文名']})")
        output.append(f"  - **初始冷却时间 (CD):** {skill_data.get('冷却时间(初始)', '未知')} 回合")

        for i, effect in enumerate(skill_data['效果']):
            effect_num = i + 1
            output.append(f"  - **效果 {effect_num}:** {effect['描述']}")
            
            if effect['等级数值']:
                # 提取等级1和等级10的数值用于简洁展示
                lv1 = effect['等级数值'].get('Lv1', 'N/A')
                lv10 = effect['等级数值'].get('Lv10', 'N/A')
                output.append(f"    - **数值范围:** Lv1 ({lv1}) → Lv10 ({lv10})")
                
                # 如果是多重效果的展示，可以展示所有等级的数值
                # output.append("    - 所有等级数值: " + " | ".join(effect['等级数值'].values()))
                
    # 2. 职阶技能
    output.append("\n## 职阶技能 (Class Skills)")
    for skill in data['职阶技能']:
        output.append(f"- **{skill['中文名']} {skill['阶级']}**")
        output.append(f"  - **效果:** {skill['效果']}")
        
    return "\n".join(output)

# --- 原始数据块 ---
raw_skill_text = """
==技能==
===持有技能===
'''技能1（初期开放）'''
{{持有技能|加攻|领袖气质 B|カリスマ B|7
|己方全体的攻击力提升(3回合)|9%|9.9%|10.8%|11.7%|12.6%|13.5%|14.4%|15.3%|16.2%|18%
}}
'''技能2（灵基再临第1阶段开放）'''
<tabber>
强化后=通关「[[阿尔托莉雅·潘德拉贡/从者任务#强化任务2|强化关卡 阿尔托莉雅·潘德拉贡 2]]」后强化。<br>
''（开放条件：达到灵基再临第4阶段。需通关「[[阿尔托莉雅·潘德拉贡/从者任务#强化任务1|强化关卡 阿尔托莉雅·潘德拉贡]]」。开放时间：[[从者强化任务 第12弹～5th Anniversary～特别篇]]。）''
{{持有技能|红放|龙之炉心 B|竜の炉心 B|7
|自身的Buster指令卡性能提升(1回合)|30%|32%|34%|36%|38%|40%|42%|44%|46%|50%
|宝具威力提升(1回合)|20%|21%|22%|23%|24%|25%|26%|27%|28%|30%
|所有指令卡变更为Buster类型(1回合)|∅|||||||||
}}
|-|
强化前=
{{持有技能|红放|魔力放出 A|魔力放出 A|7
|自身的Buster指令卡性能提升(1回合)|30%|32%|34%|36%|38%|40%|42%|44%|46%|50%
}}
</tabber>
'''技能3（灵基再临第3阶段开放）'''
<tabber>
强化后=通关「[[阿尔托莉雅·潘德拉贡/从者任务#强化任务1|强化关卡 阿尔托莉雅·潘德拉贡]]」后强化。<br>
''（开放条件：达到灵基再临第4阶段。开放时间：[[从者强化任务 第9弹～3rd Anniversary～特别篇]]。）''
{{持有技能|充能|闪耀之路 EX|輝ける路 EX|7
|自身的NP增加|20%|21%|22%|23%|24%|25%|25%|27%|28%|30%
|获得大量暴击星|5|6|7|8|9|10|11|12|13|15
}}
|-|
强化前=
{{持有技能|出星|直觉 A|直感 A|7
|获得大量暴击星|5|6|7|8|9|10|11|12|13|15
}}
</tabber>

===职阶技能===
{{职阶技能|对魔力|对魔力|A|自身的弱化耐性提升(20%)}}
{{职阶技能|骑乘|骑乘|B|自身的Quick指令卡性能提升(8%)}}

===追加技能===
{{追加技能|技能id1=3001000|技能id2=3002000|技能id3=3006000}}
"""

text2 = """
==技能==
===持有技能===
'''技能1（初期开放）'''
{{持有技能|无视防御|天威星（夏） A|天威星（夏） A|8
|付与自身无视防御状态(3回合)<!--自身に防御無視状態を付与(3ターン)-->
|∅|||||||||
|攻击力提升(3回合)<!--攻撃力をアップ(3ターン)-->
|20%|21%|22%|23%|24%|25%|26%|27%|28%|30%
|暴击星集中度提升(1回合)<!--スター集中度をアップ(1ターン)-->
|3000%|3200%|3400%|3600%|3800%|4000%|4200%|4400%|4600%|5000%
}}
'''技能2（灵基再临第1阶段开放）'''
{{持有技能|绿放|夏之认可欲望 B|夏の承認欲求 B|8
|自身的Quick指令卡性能提升(3回合)<!--自身のQuickカード性能をアップ(3ターン)-->
|10%|11%|12%|13%|14%|15%|16%|17%|18%|20%
|付与「受到HP回复效果或最大HP提升效果时<除每回合HP回复效果、概念礼装·指令纹章的效果以外>，自身的Quick指令卡性能小幅提升(最大10个·3回合)」的状态(3回合)<!--「HP回復効果または最大HPアップ効果を受けた時<毎ターンHP回復効果、概念礼装・コマンドコードによる効果を除く>に自身のQuickカード性能を少しアップ(最大10個・3ターン)」する状態を付与(3ターン)-->
|10%|||||||||
|付与回避状态(2次·3回合)<!--回避状態を付与(2回・3ターン)-->
|∅|||||||||
}}
'''技能3（灵基再临第3阶段开放）'''
{{持有技能|充能|连环马（凭依） A|連環馬（憑依） A|8
|自身的NP增加<!--自身のNPを増やす-->
|20%|21%|22%|23%|24%|25%|26%|27%|28%|30%
|暴击威力提升(3回合)<!--クリティカル威力をアップ(3ターン)-->
|20%|21%|22%|23%|24%|25%|26%|27%|28%|30%
|暴击威力大提升(1回合)<!--クリティカル威力を大アップ(1ターン)-->
|50%|55%|60%|65%|70%|75%|80%|85%|90%|100%
|获得暴击星<!--スターを獲得-->
|10|11|12|13|14|15|16|17|18|20
}}
===职阶技能===
{{职阶技能|狂化|狂化|EX|自身的Buster指令卡性能提升(12%)<!--自身のBusterカードの性能をアップ(12%)-->|红卡集星|幻兽凭依|C|自身的Buster指令卡暴击星集中度小幅提升(10%)<!--自身のBusterカードのスター集中度を少しアップ(10%)-->}}
===追加技能===
{{追加技能|技能id1=3001000|技能id2=3002000|技能id3=3022000}}"""

# --- 运行解析 ---
# parsed_skill_data = parse_noble_skills(raw_skill_text)
# print(parsed_skill_data)
# formatted_output = format_fgo_skills(parsed_skill_data)

# print(formatted_output)