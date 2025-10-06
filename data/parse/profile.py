import re
from typing import Dict, List, Any

def clean_wikitext_value(value: str) -> str:
    """清理函数，用于移除常见的Wiki语法标记。"""
    # 移除链接标记 [[...|显示文本]] -> 显示文本, [[链接]] -> 链接
    value = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', value)
    # 移除 HTML 注释 <!-- ... -->
    value = re.sub(r'<!--[\s\S]*?-->', '', value)
    # 移除 HTML 标签 <...>
    value = re.sub(r'<[^>]+>', ' ', value)
    # 移除斜体/粗体标记 ''', ''
    value = value.replace("'''", "").replace("''", "")
    # 移除多余的空白
    value = ' '.join(value.split())
    return value.strip()

def parse_noble_profiles(profile_section_text: str) -> List[Dict[str, str]]:
    """
    一个健壮的“资料”模块解析器。
    它会忽略日文部分，并将所有信息转换为一个扁平化的字典列表。
    返回格式: List[Dict[str, str]]
    """
    # 1. 首先定位到 {{个人资料...}} 模板
    profile_match = re.search(r'\{\{个人资料([\s\S]*?)\}\}', profile_section_text, re.I)
    if not profile_match:
        return [] # 如果找不到模板，返回空列表

    template_content = profile_match.group(1)
    
    # 使用逐行解析
    lines = template_content.strip().split('\n|')
    
    # 临时存储解析出的键值对
    raw_params = {}
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            # 2. 关键：直接在这里过滤掉日文内容
            if not key.endswith('日文'):
                raw_params[key] = value

    # 3. 结构化重组数据为 List[Dict[str, str]]
    
    # 这是我们最终要返回的列表
    profile_chunks = []
    
    # 首先处理独立的“详情”字段
    if '详情' in raw_params:
        cleaned_content = clean_wikitext_value(raw_params['详情'])
        if cleaned_content: # 确保内容不为空
            profile_chunks.append({
                'type': '详情',
                'content': cleaned_content,
                'condition': '默认开放'
            })
    
    # 处理按数字分组的资料条目 (资料1, 资料2, ...)
    # 通过正则表达式找到所有 '资料X' 这样的键
    data_keys = sorted([k for k in raw_params.keys() if re.match(r'^资料\d+$', k)])
    
    for key in data_keys:
        # 从 "资料1" 中提取数字 "1"
        entry_id = re.search(r'\d+', key).group()
        
        condition_key = f"资料{entry_id}条件"
        text_key = f"资料{entry_id}"
        
        content = clean_wikitext_value(raw_params.get(text_key, ""))
        
        # 只有当内容不为空时才添加
        if content:
            # 获取并清理条件
            condition = clean_wikitext_value(raw_params.get(condition_key, ""))
            # 如果条件为空，则设置为默认值
            if not condition:
                condition = "默认开放"

            profile_chunks.append({
                '类型': f'资料{entry_id}',
                '文本': content,
                '开放条件': condition
            })
        
    return profile_chunks


# --- 使用示例 ---
if __name__ == '__main__':

    profile_section_content = """
                                ==资料==
{{#ifexist:{{PAGENAME}}/从者任务|{{参阅|{{PAGENAME}}/从者任务|该从者的幕间物语和强化关卡}}}}
{{个人资料
|详情=
不列颠传说中的王。也被誉为骑士王。
阿尔托莉雅是幼名，自从当上国王之后，
就开始被称为亚瑟王了。
在骑士道凋零的时代，手持圣剑，
给不列颠带来了短暂的和平与最后的繁荣。
史实上虽为男性，
但在这个世界内却似乎是男装丽人。

|详情日文=
ブリテンの伝説の王。騎士王とも。
アルトリアは幼名であり、王として起ってからは
アーサー王と呼ばれる事になった。
騎士道が花と散った時代、聖剣を手にブリテンに
つかの間の平和と最後の繁栄をもたらした。
史実では男性だが、
この世界では男装の麗人であったようだ。

|资料1条件=
|资料1=
身高／体重：154cm·42kg
出处：亚瑟王传说
地域：英国
属性：秩序·善　　副属性：地　　性别：女性
行为举止都以男性为标准，
因此很不擅长应对异性向自己表达的好感。

|资料1日文=
身長／体重：154cm・42kg
出典：アーサー王伝説
地域：イギリス
属性：秩序・善　　副属性：地　　性別：女性
男性として振舞ってきたため異性からの好意には疎い。

|资料2条件=
|资料2=
崇尚万人眼中正确生活、正确人生的
理想王者之一。
锄强扶弱，是个无可非议的人物。
冷静沉着，无论何时都十分认真的优等生。
尽管如此……虽说从不愿意开口承认，
但她却有着不服输的一面。对任何需要一争高下的事
都不会手下留情，一旦败北则会非常懊悔。

|资料2日文=
万人にとって善き生活、善き人生を善しとする
理想の王のひとり。
弱きを助け強きをくじく非の打ち所のない人物。
冷静沈着、どんな時でも真面目な優等生。
……なのだが、口には出さないものの負けず嫌い
なところがあり、およそすべての勝負事には手を
抜かず、負けるとたいへん悔しがる。

|资料3条件=
|资料3=
领袖气质：B
具有指挥军团的天生才能。
在团体战斗中，可令我军的能力提升。
贯彻清廉正直，大公无私的王。
其公正令骑士们愿意守护于她的身旁，
令民众们在对贫困的忍耐中看到了希望。
她的王者之路并不是为了统帅少数强者，
而是为了领导更多无力之人而存在的。

|资料3日文=
○カリスマ：Ｂ
軍団を指揮する天性の才能。
団体戦闘において、自軍の能力を向上させる。
清廉潔白、滅私奉公を貫いた王。
その正しさに騎士たちはかしずき、
民たちは貧窮に耐える希望を見た。
彼女の王道はひとにぎりの強者たちではなく、
より多くの、力持たぬものたちを治めるためのものだった。

|资料4条件=
|资料4=
『誓约胜利之剑』
阶级：A++　种类：对城宝具
Excalibur。
这并非人造的武器，而是由星锻造而成神造兵器。
立于圣剑顶点的宝具。
拥有真正强大力量的应是剑鞘，
而不是剑本身，但剑鞘据说已永远遗失了。

|资料4日文=
『約束された勝利の剣』
ランク：Ａ＋＋　種別：対城宝具
エクスカリバー。
人造による武器ではなく、星に鍛えられた神造兵装。
聖剣の中では頂点に立つ宝具。
真に優れた能力は剣ではなく鞘にあるのだが、その鞘は永遠に失われてしまったとされる。

|资料5条件=
|资料5=
亚瑟王传说以骑士时代的终结为结局。
亚瑟王虽然击退了异民族，
但却无法回避不列颠土地的毁灭。
圆桌骑士之一·莫德雷德的反叛
导致国家一分为二，骑士之城卡美洛也失去了其辉煌。

|资料5日文=
アーサー王伝説の最後は騎士の時代の終わりである。
アーサー王は異民族たちを撃退したものの、
ブリテンの土地は滅びを回避できなかった。
円卓の騎士のひとり・モードレッドの叛逆によって国は
二つに割れ、騎士たちの城キャメロットはその光を失った。

|资料6条件=
通关 [[阿尔托莉雅·潘德拉贡/从者任务#幕间物语1|战斗的理由]]后开放

|资料6=
亚瑟王在卡姆兰之丘成功讨伐了莫德雷德，
自己却也因负重伤而倒下。在去世前，
她将圣剑
交给了最后的心腹贝德维尔，离开了这个世界。
死后她被送往了理想乡——不存于此世的乐园·阿瓦隆，
并打算在遥远的未来再次拯救不列颠。

|资料6日文=
アーサー王はカムランの丘でモードレッドを討ち滅ぼすも、自らも傷を負い膝を折った。
息を引き取る直前、最後の腹心ベディヴィエールに聖剣を預け、現世から退場する。
死後は理想郷―――この世界のどこにもない楽園・アヴァロンに運ばれ、遠い未来、再びブリテンを救うとされている。

}}
"""
            
    # parsed_profile = parse_noble_profiles(profile_section_content)
        
    # import json
    # print(json.dumps(parsed_profile, indent=2, ensure_ascii=False))