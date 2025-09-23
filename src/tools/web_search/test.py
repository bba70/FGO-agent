# === 网络搜索信息提取与大模型集成方案 ===

"""
完整的网络搜索信息提取流程：
1. 搜索结果获取
2. 网页内容提取
3. 内容清理和结构化
4. 长度控制和优化
5. 大模型集成策略
"""

import asyncio
import httpx
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse, quote
from dataclasses import dataclass
from datetime import datetime
import hashlib

# 核心依赖库
from bs4 import BeautifulSoup
from readability import Document
import tiktoken
from newspaper import Article
import trafilatura

# ===== 第一部分：搜索结果获取 =====

@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    source: str
    rank: int = 0
    timestamp: datetime = None

class WebSearchEngine:
    """网络搜索引擎封装"""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            follow_redirects=True
        )
    
    async def search_duckduckgo(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """使用DuckDuckGo搜索"""
        try:
            # DuckDuckGo HTML搜索（更可靠的方法）
            search_url = "https://html.duckduckgo.com/html/"
            params = {
                'q': query,
                'b': '',  # 起始位置
                'kl': 'cn-zh',  # 中文地区
                's': '0'  # 排序方式
            }
            
            response = await self.http_client.post(search_url, data=params)
            response.raise_for_status()
            
            return self._parse_duckduckgo_html(response.text, max_results)
        
        except Exception as e:
            logging.error(f"DuckDuckGo搜索失败: {e}")
            return []
    
    def _parse_duckduckgo_html(self, html: str, max_results: int) -> List[SearchResult]:
        """解析DuckDuckGo HTML结果"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # 查找搜索结果容器
        result_containers = soup.find_all('div', class_='result')
        
        for i, container in enumerate(result_containers[:max_results]):
            try:
                # 提取标题和链接
                title_link = container.find('a', class_='result__a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                url = title_link.get('href', '')
                
                # 提取描述
                snippet_elem = container.find('a', class_='result__snippet')
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                
                if title and url:
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="duckduckgo",
                        rank=i + 1,
                        timestamp=datetime.now()
                    ))
            
            except Exception as e:
                logging.warning(f"解析搜索结果项失败: {e}")
                continue
        
        return results
    
    async def search_with_google_api(self, query: str, api_key: str, cx: str, max_results: int = 10) -> List[SearchResult]:
        """使用Google Custom Search API"""
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': api_key,
                'cx': cx,
                'q': query,
                'num': min(max_results, 10),  # Google API最多10个结果
                'hl': 'zh-CN',
                'gl': 'cn'
            }
            
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for i, item in enumerate(data.get('items', [])):
                results.append(SearchResult(
                    title=item.get('title', ''),
                    url=item.get('link', ''),
                    snippet=item.get('snippet', ''),
                    source="google_api",
                    rank=i + 1,
                    timestamp=datetime.now()
                ))
            
            return results
        
        except Exception as e:
            logging.error(f"Google搜索失败: {e}")
            return []

# ===== 第二部分：网页内容提取 =====

@dataclass
class ExtractedContent:
    """提取的网页内容"""
    url: str
    title: str
    content: str
    summary: str
    metadata: Dict[str, Any]
    extraction_method: str
    token_count: int
    quality_score: float

class WebContentExtractor:
    """网页内容提取器"""
    
    def __init__(self, token_limit: int = 4000):
        self.token_limit = token_limit
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ContentBot/1.0)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate'
            }
        )
    
    async def extract_multiple_urls(self, urls: List[str], max_concurrent: int = 3) -> List[ExtractedContent]:
        """并发提取多个URL的内容"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(url):
            async with semaphore:
                return await self.extract_content(url)
        
        tasks = [extract_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_results = []
        for result in results:
            if isinstance(result, ExtractedContent):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logging.warning(f"内容提取失败: {result}")
        
        return valid_results
    
    async def extract_content(self, url: str) -> Optional[ExtractedContent]:
        """提取单个URL的内容（多方法尝试）"""
        methods = [
            ("trafilatura", self._extract_with_trafilatura),
            ("newspaper", self._extract_with_newspaper),
            ("readability", self._extract_with_readability),
            ("beautifulsoup", self._extract_with_bs4)
        ]
        
        for method_name, method_func in methods:
            try:
                content = await method_func(url)
                if content and content.quality_score > 0.3:  # 质量阈值
                    content.extraction_method = method_name
                    return content
            except Exception as e:
                logging.debug(f"方法 {method_name} 提取失败 {url}: {e}")
                continue
        
        logging.warning(f"所有提取方法都失败了: {url}")
        return None
    
    async def _extract_with_trafilatura(self, url: str) -> Optional[ExtractedContent]:
        """使用trafilatura提取（推荐方法）"""
        response = await self.http_client.get(url)
        response.raise_for_status()
        
        # 使用trafilatura提取
        content = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            include_formatting=False
        )
        
        if not content:
            return None
        
        # 提取元数据
        metadata = trafilatura.extract_metadata(response.text)
        title = metadata.title if metadata and metadata.title else self._extract_title_from_html(response.text)
        
        # 计算质量得分
        quality_score = self._calculate_content_quality(content, len(response.text))
        
        # 生成摘要
        summary = self._generate_summary(content, max_length=200)
        
        # 计算token数量
        token_count = len(self.tokenizer.encode(content))
        
        return ExtractedContent(
            url=url,
            title=title or "无标题",
            content=content,
            summary=summary,
            metadata=metadata.__dict__ if metadata else {},
            extraction_method="trafilatura",
            token_count=token_count,
            quality_score=quality_score
        )
    
    async def _extract_with_newspaper(self, url: str) -> Optional[ExtractedContent]:
        """使用newspaper3k提取"""
        article = Article(url, language='zh')
        await asyncio.to_thread(article.download)
        await asyncio.to_thread(article.parse)
        
        if not article.text:
            return None
        
        content = article.text
        quality_score = self._calculate_content_quality(content, len(article.html))
        summary = self._generate_summary(content, max_length=200)
        token_count = len(self.tokenizer.encode(content))
        
        return ExtractedContent(
            url=url,
            title=article.title or "无标题",
            content=content,
            summary=summary,
            metadata={
                "authors": article.authors,
                "publish_date": str(article.publish_date) if article.publish_date else None,
                "top_image": article.top_image
            },
            extraction_method="newspaper",
            token_count=token_count,
            quality_score=quality_score
        )
    
    async def _extract_with_readability(self, url: str) -> Optional[ExtractedContent]:
        """使用readability提取"""
        response = await self.http_client.get(url)
        response.raise_for_status()
        
        doc = Document(response.text)
        title = doc.title()
        content_html = doc.summary()
        
        # 转换为纯文本
        soup = BeautifulSoup(content_html, 'html.parser')
        content = soup.get_text(separator='\n', strip=True)
        
        if not content:
            return None
        
        quality_score = self._calculate_content_quality(content, len(response.text))
        summary = self._generate_summary(content, max_length=200)
        token_count = len(self.tokenizer.encode(content))
        
        return ExtractedContent(
            url=url,
            title=title or "无标题",
            content=content,
            summary=summary,
            metadata={},
            extraction_method="readability",
            token_count=token_count,
            quality_score=quality_score
        )
    
    async def _extract_with_bs4(self, url: str) -> Optional[ExtractedContent]:
        """使用BeautifulSoup提取（兜底方法）"""
        response = await self.http_client.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 移除脚本和样式
        for element in soup(["script", "style", "nav", "footer", "aside"]):
            element.decompose()
        
        # 提取标题
        title = self._extract_title_from_html(response.text)
        
        # 提取主要内容区域
        content_candidates = soup.find_all(['article', 'main', 'div'], 
                                         class_=re.compile(r'content|article|post|main', re.I))
        
        if content_candidates:
            content = content_candidates[0].get_text(separator='\n', strip=True)
        else:
            content = soup.get_text(separator='\n', strip=True)
        
        # 清理内容
        content = self._clean_text(content)
        
        if not content:
            return None
        
        quality_score = self._calculate_content_quality(content, len(response.text))
        summary = self._generate_summary(content, max_length=200)
        token_count = len(self.tokenizer.encode(content))
        
        return ExtractedContent(
            url=url,
            title=title or "无标题",
            content=content,
            summary=summary,
            metadata={},
            extraction_method="beautifulsoup",
            token_count=token_count,
            quality_score=quality_score
        )
    
    def _extract_title_from_html(self, html: str) -> str:
        """从HTML中提取标题"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 尝试多种标题提取方法
        title_candidates = [
            soup.find('title'),
            soup.find('h1'),
            soup.find('meta', property='og:title'),
            soup.find('meta', name='title')
        ]
        
        for candidate in title_candidates:
            if candidate:
                if candidate.name == 'meta':
                    title = candidate.get('content', '').strip()
                else:
                    title = candidate.get_text(strip=True)
                
                if title:
                    return title[:100]  # 限制标题长度
        
        return ""
    
    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        # 移除多余的空白
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # 移除常见的无用内容
        patterns_to_remove = [
            r'Cookie.*?同意',
            r'订阅.*?newsletter',
            r'关注我们.*?社交媒体',
            r'版权所有.*?保留',
            r'广告',
            r'Advertisement'
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _calculate_content_quality(self, content: str, html_length: int) -> float:
        """计算内容质量得分"""
        if not content:
            return 0.0
        
        # 内容长度得分（适中长度得分高）
        length_score = min(len(content) / 1000, 1.0) if len(content) > 100 else 0.1
        
        # 内容密度得分（文本内容占HTML的比例）
        density_score = len(content) / max(html_length, 1) if html_length > 0 else 0.5
        
        # 结构化得分（包含段落、句子的结构化程度）
        structure_score = min(content.count('\n') / 10, 1.0) + min(content.count('.') / 20, 1.0)
        
        # 综合得分
        return (length_score * 0.4 + density_score * 0.3 + structure_score * 0.3)
    
    def _generate_summary(self, content: str, max_length: int = 200) -> str:
        """生成内容摘要"""
        sentences = re.split(r'[。！？.!?]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        summary = ""
        for sentence in sentences[:3]:  # 取前3句
            if len(summary) + len(sentence) <= max_length:
                summary += sentence + "。"
            else:
                break
        
        return summary.strip()

# ===== 第三部分：内容长度控制与优化 =====

class ContentOptimizer:
    """内容长度控制与优化器"""
    
    def __init__(self, max_tokens: int = 4000, reserve_tokens: int = 1000):
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens  # 为对话历史预留的token
        self.available_tokens = max_tokens - reserve_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def optimize_content_for_llm(self, extracted_contents: List[ExtractedContent], query: str) -> str:
        """优化提取的内容以适应LLM上下文限制"""
        
        if not extracted_contents:
            return "未找到相关内容"
        
        # 1. 按质量排序
        sorted_contents = sorted(extracted_contents, 
                                key=lambda x: x.quality_score, reverse=True)
        
        # 2. 计算查询的token消耗
        query_tokens = len(self.tokenizer.encode(query))
        remaining_tokens = self.available_tokens - query_tokens - 200  # 预留格式化token
        
        # 3. 智能选择和截取内容
        optimized_parts = []
        used_tokens = 0
        
        for i, content in enumerate(sorted_contents):
            if used_tokens >= remaining_tokens:
                break
            
            # 为每个来源分配token预算
            source_budget = min(
                remaining_tokens - used_tokens,
                remaining_tokens // max(len(sorted_contents) - i, 1)
            )
            
            # 提取关键部分
            key_content = self._extract_key_content(content, query, source_budget)
            
            if key_content:
                content_tokens = len(self.tokenizer.encode(key_content))
                if used_tokens + content_tokens <= remaining_tokens:
                    optimized_parts.append({
                        'title': content.title,
                        'url': content.url,
                        'content': key_content,
                        'tokens': content_tokens
                    })
                    used_tokens += content_tokens
        
        # 4. 格式化最终内容
        return self._format_optimized_content(optimized_parts, query)
    
    def _extract_key_content(self, content: ExtractedContent, query: str, token_budget: int) -> str:
        """提取与查询最相关的内容片段"""
        full_text = content.content
        query_terms = set(query.lower().split())
        
        # 分段
        paragraphs = [p.strip() for p in full_text.split('\n') if len(p.strip()) > 50]
        
        if not paragraphs:
            return full_text[:token_budget * 3]  # 粗略估算字符数
        
        # 计算每段的相关性得分
        scored_paragraphs = []
        for para in paragraphs:
            score = self._calculate_relevance_score(para, query_terms)
            tokens = len(self.tokenizer.encode(para))
            scored_paragraphs.append({
                'text': para,
                'score': score,
                'tokens': tokens
            })
        
        # 按相关性排序
        scored_paragraphs.sort(key=lambda x: x['score'], reverse=True)
        
        # 选择最相关的段落
        selected_content = []
        used_tokens = 0
        
        for para in scored_paragraphs:
            if used_tokens + para['tokens'] <= token_budget:
                selected_content.append(para['text'])
                used_tokens += para['tokens']
            elif used_tokens < token_budget * 0.8:  # 如果还有较多预算，尝试截取
                remaining = token_budget - used_tokens
                truncated = self._truncate_to_tokens(para['text'], remaining)
                if truncated:
                    selected_content.append(truncated)
                break
        
        return '\n'.join(selected_content)
    
    def _calculate_relevance_score(self, text: str, query_terms: set) -> float:
        """计算文本与查询的相关性得分"""
        text_lower = text.lower()
        text_words = set(text_lower.split())
        
        # 词汇匹配得分
        exact_matches = len(query_terms.intersection(text_words))
        partial_matches = sum(1 for term in query_terms 
                            if any(term in word for word in text_words))
        
        # 位置得分（查询词在文本开头的权重更高）
        position_score = 0
        for term in query_terms:
            pos = text_lower.find(term)
            if pos >= 0:
                position_score += max(0, 1 - pos / len(text))
        
        # 综合得分
        vocab_score = (exact_matches * 2 + partial_matches) / len(query_terms)
        total_score = vocab_score * 0.7 + position_score * 0.3
        
        return total_score
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """按token数量截取文本"""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens) + "..."
    
    def _format_optimized_content(self, content_parts: List[Dict], query: str) -> str:
        """格式化优化后的内容"""
        if not content_parts:
            return f"抱歉，没有找到与 '{query}' 相关的有效内容。"
        
        formatted_parts = [f"基于搜索查询 '{query}' 找到以下相关信息：\n"]
        
        for i, part in enumerate(content_parts, 1):
            formatted_parts.append(f"""
【来源 {i}】{part['title']}
链接：{part['url']}
内容：{part['content']}
""")
        
        # 添加token使用统计
        total_tokens = sum(part['tokens'] for part in content_parts)
        formatted_parts.append(f"\n[信息来源数量: {len(content_parts)} | 内容tokens: {total_tokens}]")
        
        return "\n".join(formatted_parts)

# ===== 第四部分：完整的搜索工具集成 ===

class IntelligentWebSearch:
    """智能网络搜索工具"""
    
    def __init__(self, max_results: int = 5, max_content_tokens: int = 4000):
        self.search_engine = WebSearchEngine()
        self.content_extractor = WebContentExtractor()
        self.content_optimizer = ContentOptimizer(max_tokens=max_content_tokens)
        self.max_results = max_results
    
    async def search_and_extract(self, query: str, extract_content: bool = True) -> Dict[str, Any]:
        """执行完整的搜索和内容提取流程"""
        
        try:
            # 1. 执行搜索
            search_results = await self.search_engine.search_duckduckgo(query, self.max_results)
            
            if not search_results:
                return {
                    "success": False,
                    "message": f"没有找到关于 '{query}' 的搜索结果",
                    "results": []
                }
            
            result = {
                "success": True,
                "query": query,
                "search_results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "rank": r.rank
                    }
                    for r in search_results
                ],
                "extracted_contents": []
            }
            
            if not extract_content:
                return result
            
            # 2. 提取内容
            urls_to_extract = [r.url for r in search_results[:3]]  # 只提取前3个结果
            extracted_contents = await self.content_extractor.extract_multiple_urls(urls_to_extract)
            
            result["extracted_contents"] = [
                {
                    "title": content.title,
                    "url": content.url,
                    "summary": content.summary,
                    "token_count": content.token_count,
                    "quality_score": content.quality_score,
                    "extraction_method": content.extraction_method
                }
                for content in extracted_contents
            ]
            
            # 3. 优化内容
            if extracted_contents:
                optimized_content = self.content_optimizer.optimize_content_for_llm(
                    extracted_contents, query
                )
                result["optimized_content"] = optimized_content
            else:
                result["optimized_content"] = "无法提取网页内容，仅提供搜索结果摘要。"
            
            return result
        
        except Exception as e:
            logging.error(f"搜索和提取失败: {e}")
            return {
                "success": False,
                "message": f"搜索过程中发生错误: {str(e)}",
                "results": []
            }
    
    async def close(self):
        """关闭资源"""
        await self.search_engine.http_client.aclose()
        await self.content_extractor.http_client.aclose()

# ===== 使用示例 ===

async def demo_intelligent_search():
    """智能搜索演示"""
    
    search_tool = IntelligentWebSearch(max_results=5, max_content_tokens=3000)
    
    try:
        # 测试查询
        query = "FGO奥博龙配队"
        
        print(f"🔍 搜索查询: {query}")
        result = await search_tool.search_and_extract(query, extract_content=True)
        
        if result["success"]:
            print(f"\n✅ 搜索成功!")
            print(f"📊 找到 {len(result['search_results'])} 个搜索结果")
            print(f"📄 提取了 {len(result['extracted_contents'])} 个网页内容")
            
            print(f"\n📝 优化后的内容 (用于LLM):")
            print("=" * 80)
            print(result["optimized_content"])
            print("=" * 80)
        else:
            print(f"❌ 搜索失败: {result['message']}")
    
    finally:
        await search_tool.close()

# ===== 与LangGraph集成的节点示例 ===

async def create_web_search_node(search_tool: IntelligentWebSearch):
    """创建网络搜索节点"""
    
    async def web_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """网络搜索节点实现"""
        
        query = state.get("tool_input", {}).get("query", "")
        
        if not query:
            error_message = "搜索查询不能为空"
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": error_message}],
                "tool_result": {"success": False, "error": error_message}
            }
        
        # 执行搜索和内容提取
        search_result = await search_tool.search_and_extract(query, extract_content=True)
        
        if search_result["success"]:
            # 使用优化后的内容
            response_content = search_result["optimized_content"]
            
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": response_content}],
                "tool_result": {
                    "success": True,
                    "answer": response_content,
                    "type": "web_search",
                    "sources": len(search_result["search_results"])
                }
            }
        else:
            error_message = search_result["message"]
            return {
                "messages": state["messages"] + [{"role": "assistant", "content": error_message}],
                "tool_result": {"success": False, "error": error_message}
            }
    
    return web_search_node

if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo_intelligent_search())