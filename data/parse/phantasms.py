import re
from typing import Dict, List, Any

def remove_japanese(text):
    """
    从字符串中移除所有日文字符（平假名、片假名和汉字）。

    参数:
    text (str): 包含日文字符的字符串。

    返回:
    str: 移除了日文字符后的字符串。
    """
    # 匹配平假名、片假名和常用汉字的正则表达式
    # 注意，这个表达式包含了大部分日文书写系统中的字符
    japanese_pattern = re.compile(
        r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3000-\u303F]'
    )
    cleaned_text = japanese_pattern.sub('', text)
    
    return cleaned_text

def parse_phantasms(text_block):
    """
    解析 FGO 维基宝具数据块，将数据提取到结构化字典中。

    参数:
    text_block (str): 包含宝具信息的原始文本块。

    返回:
    dict: 包含结构化宝具数据的字典。
    """
    data = {}
    
    # 移除所有 Wiki 标记和换行符，以便于正则匹配
    cleaned_text = re.sub(r'\{\{.*?\}\}|\[\[.*?\]\]|\<br\>', '', text_block)
    # 将所有的 | 替换成换行符，便于按行解析
    cleaned_text = cleaned_text.replace('|', '\n')

    # print('解析宝具数据', cleaned_text)
    # print('='*100)

    lines = cleaned_text.split('\n')
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if len(key) ==  0 or len(value) == 0:
                continue
            data[key] = value

    for key in data.keys():
        if len(key) > 2  and key[:2] == '数值':
            # 获取效果
            effect = data[f"效果{key[2]}"]
            data[key] = f"宝具等级为{key[-1]}时,{effect},数值为{data[key]}"
            
    
    return data

def parse_noble_phantasms(np_section_text: str) -> List[Dict[str, Any]]:
    """宝具解析器"""
    noble_phantasms = []
    
    # 存在 <tabber>
    if '<tabber>' in np_section_text.lower():
        # 移除 <tabber> 和 </tabber> 标签本身，以便于分割
        content_inside_tabber = re.search(r'<tabber>([\s\S]*?)</tabber>', np_section_text, re.I).group(1)
        
        # 使用 '|-|' 作为分隔符，分割出不同的版本块
        version_blocks = content_inside_tabber.split('|-|')
        
        for block in version_blocks:
            # print("block:", block)
            block = block.strip()
            if not block:
                continue

            # 识别版本状态
            first_line = block.split('\n', 1)[0]
            status = "未知版本"
            if '强化后' in first_line:
                status = '强化后'
            elif '强化前' in first_line:
                status = '强化前'
            elif '再强化' in first_line:
                status = '再强化后'
            else:
                # 如果第一行没有明确标识，我们可以从 '=' 左边提取
                match = re.match(r'([^=]+)=', first_line)
                if match:
                    status = match.group(1).strip()
            
            # 在这个版本块中寻找 {{宝具}} 模板
            np_match = re.search(r'\{\{宝具([\s\S]*?)\}\}', block, re.I)
            if np_match:
                np_content = np_match.group(1)
                parsed_np = parse_phantasms(np_content)
                noble_phantasms.append({
                    status: parsed_np
                })

    # 没有<tabber>
    else:
        # print('没有加强',np_section_text)
        np_matches = re.findall(r'\{\{宝具([\s\S]*?)\}\}', np_section_text, re.I)
        for np_content in np_matches:
            # print("没有加强", np_content)
            parsed_np = parse_phantasms(np_content)
            noble_phantasms.append({
                status: parsed_np
            })
            
    return noble_phantasms

def format_fgo_servant_data(data):
    """
    将结构化数据格式化为易于阅读的文本。
    """
    output_lines = []
    
    # 格式化基本信息
    output_lines.append(f"宝具名称：{data.get('中文名', '未知')}")
    output_lines.append(f"卡牌颜色：{data.get('卡色', '未知')}")
    output_lines.append(f"宝具种类：{data.get('种类', '未知')}")
    output_lines.append("-" * 20)
    
    # 格式化所有效果
    for effect_key, effect_data in data['效果'].items():
        description = effect_data['描述']
        values = effect_data['数值']
        scaling_type = effect_data['数值类型']
        
        if scaling_type == '固定':
            output_lines.append(f"{effect_key}：{description}")
        else:
            output_lines.append(f"{effect_key}：{description}")
            for level, value in values.items():
                if scaling_type == '宝具等级':
                    output_lines.append(f"  - 宝具等级 {level} 时，数值为 {value}")
                elif scaling_type == 'Over Charge':
                    # 也可以根据 level 映射到 OC 百分比
                    oc_percent = f"{level}00%"
                    output_lines.append(f"  - Over Charge {oc_percent} 时，数值为 {value}")
    
    return "\n".join(output_lines)

raw_text = """
{{参阅2|{{BiliSearch|{{PAGENAME}} 宝具动画|Bilibili搜索}}|该从者的宝具动画}}
{{宝具
|中文名=大降临连环马猛袭击
|国服上标=Daikourin Renkanba Moushugeki
|日文名=大降臨連環馬猛襲撃
|日服上标=だいこうりんれんかんばもうしゅうげき
|卡色=Quick
|类型=全体
|阶级=A
|种类=对军宝具
|效果A=对敌方全体发动强大的攻击<宝具升级效果提升><!--敵全体に強力な〔秩序〕特攻攻撃<宝具升级效果提升>-->
|数值A1=600%|数值A2=800%|数值A3=900%|数值A4=950%|数值A5=1000%
|效果B=对{{特攻|秩序|前缀=属性|类型=宝具}}特攻<Over Charge时特攻威力提升><!--<Over Chargeで特攻威力アップ>-->
|数值B1=150%|数值B2=162.5%|数值B3=175%|数值B4=187.5%|数值B5=200%
|效果C=低概率付与眩晕状态(1回合)<!--(30%概率)低確率でスタン状態を付与(1ターン)-->
|数值C1=30%
|效果D=暴击发生率下降(3回合)<!--クリティカル発生率をダウン(3ターン)-->
|数值D1=20%
}}
"""

# parsed_data = parse_fgo_servant_data(raw_text)
