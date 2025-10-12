# === web_search_fastmcp.py ===

import asyncio
import os
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from readability import Document
import tiktoken
import trafilatura
from newspaper import Article
from dotenv import load_dotenv

from fastmcp import FastMCP

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web-search-mcp")


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    source: str
    rank: int = 0

@dataclass
class ExtractedContent:
    """提取的网页内容"""
    url: str
    title: str
    content: str
    summary: str
    extraction_method: str
    token_count: int
    quality_score: float



class WebSearchTool:
    """网络搜索工具核心类"""
    
    def __init__(self):
        self.max_results = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
        self.max_tokens = int(os.getenv("MAX_CONTENT_TOKENS", "4000"))
        self.timeout = int(os.getenv("TIMEOUT_SECONDS", "20"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Google API配置（可选）
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cx = os.getenv("GOOGLE_CX")
        
        # HTTP客户端
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate'
            },
            follow_redirects=True
        )
        
        # Token计算器
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        if self.debug:
            logger.setLevel(logging.DEBUG)
    
    async def search_web(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """执行网络搜索"""
        if max_results is None:
            max_results = self.max_results
        
        logger.info(f"开始搜索: {query}")
        
        try:
            # 优先使用Google API（如果配置了）
            if self.google_api_key and self.google_cx:
                results = await self._search_with_google(query, max_results)
                if results:
                    return results
            
            # 使用DuckDuckGo作为后备
            return await self._search_with_duckduckgo(query, max_results)
        
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    async def _search_with_google(self, query: str, max_results: int) -> List[SearchResult]:
        """使用Google Custom Search API"""
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_api_key,
                'cx': self.google_cx,
                'q': query,
                'num': min(max_results, 10),
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
                    rank=i + 1
                ))
            
            logger.info(f"Google搜索返回 {len(results)} 个结果")
            return results
        
        except Exception as e:
            logger.warning(f"Google搜索失败: {e}")
            return []
    
    async def _search_with_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """使用DuckDuckGo搜索"""
        try:
            search_url = "https://html.duckduckgo.com/html/"
            params = {
                'q': query,
                'b': '',
                'kl': 'cn-zh',
                's': '0'
            }
            
            response = await self.http_client.post(search_url, data=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # 查找搜索结果
            result_containers = soup.find_all('div', class_='result')
            
            for i, container in enumerate(result_containers[:max_results]):
                try:
                    title_link = container.find('a', class_='result__a')
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    url = title_link.get('href', '')
                    
                    snippet_elem = container.find('a', class_='result__snippet')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    if title and url:
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source="duckduckgo",
                            rank=i + 1
                        ))
                
                except Exception as e:
                    logger.debug(f"解析搜索结果失败: {e}")
                    continue
            
            logger.info(f"DuckDuckGo搜索返回 {len(results)} 个结果")
            return results
        
        except Exception as e:
            logger.error(f"DuckDuckGo搜索失败: {e}")
            return []
    
    async def extract_content(self, url: str) -> Optional[ExtractedContent]:
        """提取网页内容"""
        logger.debug(f"开始提取内容: {url}")
        
        extraction_methods = [
            ("trafilatura", self._extract_with_trafilatura),
            ("newspaper", self._extract_with_newspaper),
            ("readability", self._extract_with_readability),
            ("beautifulsoup", self._extract_with_bs4)
        ]
        
        for method_name, method_func in extraction_methods:
            try:
                content = await method_func(url)
                if content and content.quality_score > 0.3:
                    logger.debug(f"使用 {method_name} 成功提取内容")
                    return content
            except Exception as e:
                logger.debug(f"{method_name} 提取失败: {e}")
                continue
        
        logger.warning(f"所有提取方法都失败: {url}")
        return None
    
    async def _extract_with_trafilatura(self, url: str) -> Optional[ExtractedContent]:
        """使用trafilatura提取"""
        response = await self.http_client.get(url)
        response.raise_for_status()
        
        content = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            include_formatting=False
        )
        
        if not content:
            return None
        
        metadata = trafilatura.extract_metadata(response.text)
        title = metadata.title if metadata and metadata.title else self._extract_title(response.text)
        
        return ExtractedContent(
            url=url,
            title=title or "无标题",
            content=content,
            summary=self._generate_summary(content),
            extraction_method="trafilatura",
            token_count=len(self.tokenizer.encode(content)),
            quality_score=self._calculate_quality(content, len(response.text))
        )
    
    async def _extract_with_newspaper(self, url: str) -> Optional[ExtractedContent]:
        """使用newspaper3k提取"""
        article = Article(url, language='zh')
        await asyncio.to_thread(article.download)
        await asyncio.to_thread(article.parse)
        
        if not article.text:
            return None
        
        return ExtractedContent(
            url=url,
            title=article.title or "无标题",
            content=article.text,
            summary=self._generate_summary(article.text),
            extraction_method="newspaper",
            token_count=len(self.tokenizer.encode(article.text)),
            quality_score=self._calculate_quality(article.text, len(article.html or ""))
        )
    
    async def _extract_with_readability(self, url: str) -> Optional[ExtractedContent]:
        """使用readability提取"""
        response = await self.http_client.get(url)
        response.raise_for_status()
        
        doc = Document(response.text)
        content_html = doc.summary()
        
        soup = BeautifulSoup(content_html, 'html.parser')
        content = soup.get_text(separator='\n', strip=True)
        
        if not content:
            return None
        
        return ExtractedContent(
            url=url,
            title=doc.title() or "无标题",
            content=content,
            summary=self._generate_summary(content),
            extraction_method="readability",
            token_count=len(self.tokenizer.encode(content)),
            quality_score=self._calculate_quality(content, len(response.text))
        )
    
    async def _extract_with_bs4(self, url: str) -> Optional[ExtractedContent]:
        """使用BeautifulSoup提取"""
        response = await self.http_client.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 移除无用元素
        for element in soup(["script", "style", "nav", "footer", "aside"]):
            element.decompose()
        
        title = self._extract_title(response.text)
        
        # 提取主要内容
        content_candidates = soup.find_all(['article', 'main', 'div'], 
                                         class_=re.compile(r'content|article|post|main', re.I))
        
        if content_candidates:
            content = content_candidates[0].get_text(separator='\n', strip=True)
        else:
            content = soup.get_text(separator='\n', strip=True)
        
        content = self._clean_text(content)
        
        if not content:
            return None
        
        return ExtractedContent(
            url=url,
            title=title or "无标题",
            content=content,
            summary=self._generate_summary(content),
            extraction_method="beautifulsoup",
            token_count=len(self.tokenizer.encode(content)),
            quality_score=self._calculate_quality(content, len(response.text))
        )
    
    def _extract_title(self, html: str) -> str:
        """提取标题"""
        soup = BeautifulSoup(html, 'html.parser')
        
        for selector in ['title', 'h1', 'meta[property="og:title"]']:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text(strip=True)
                if title:
                    return title[:100]
        return ""
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
    
    def _generate_summary(self, content: str, max_length: int = 200) -> str:
        """生成摘要"""
        sentences = re.split(r'[。！？.!?]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        summary = ""
        for sentence in sentences[:3]:
            if len(summary) + len(sentence) <= max_length:
                summary += sentence + "。"
            else:
                break
        
        return summary.strip()
    
    def _calculate_quality(self, content: str, html_length: int) -> float:
        """计算内容质量"""
        if not content:
            return 0.0
        
        length_score = min(len(content) / 1000, 1.0) if len(content) > 100 else 0.1
        density_score = len(content) / max(html_length, 1) if html_length > 0 else 0.5
        
        return (length_score * 0.6 + density_score * 0.4)
    
    def optimize_content_for_llm(self, extracted_contents: List[ExtractedContent], query: str) -> str:
        """优化内容长度以适应LLM"""
        if not extracted_contents:
            return f"未找到关于 '{query}' 的相关内容。"
        
        # 按质量排序
        sorted_contents = sorted(extracted_contents, key=lambda x: x.quality_score, reverse=True)
        
        # 计算可用token
        query_tokens = len(self.tokenizer.encode(query))
        available_tokens = self.max_tokens - query_tokens - 300  # 预留格式化token
        
        # 构建优化内容
        result_parts = [f"基于搜索 '{query}' 找到以下信息：\n"]
        used_tokens = len(self.tokenizer.encode(result_parts[0]))
        
        for i, content in enumerate(sorted_contents):
            if used_tokens >= available_tokens:
                break
            
            # 为每个来源分配token预算
            remaining_tokens = available_tokens - used_tokens
            source_budget = min(remaining_tokens, remaining_tokens // (len(sorted_contents) - i))
            
            # 截取内容
            content_text = content.content
            content_tokens = len(self.tokenizer.encode(content_text))
            
            if content_tokens > source_budget:
                # 截取到合适长度
                tokens = self.tokenizer.encode(content_text)
                truncated_tokens = tokens[:source_budget - 10]  # 预留"..."的token
                content_text = self.tokenizer.decode(truncated_tokens) + "..."
            
            source_info = f"""
【来源 {i+1}】{content.title}
链接：{content.url}
内容：{content_text}
"""
            
            source_tokens = len(self.tokenizer.encode(source_info))
            if used_tokens + source_tokens <= available_tokens:
                result_parts.append(source_info)
                used_tokens += source_tokens
        
        final_content = "\n".join(result_parts)
        
        # 添加统计信息
        final_content += f"\n[使用了 {len([p for p in result_parts if p.startswith('【来源')])} 个信息源]"
        
        return final_content
    
    async def close(self):
        """关闭资源"""
        await self.http_client.aclose()




# 创建全局工具实例
web_search_tool = WebSearchTool()

mcp = FastMCP("web-search-mcp")


@mcp.tool()
async def search_web(query: str, max_results: int = 5) -> str:
    """
    在网络上搜索信息并返回搜索结果
    
    Args:
        query: 搜索查询词（必填）
        max_results: 最大搜索结果数量，默认5，范围1-10
    
    Returns:
        格式化的搜索结果字符串
    """
    if not query or not query.strip():
        return "错误: 搜索查询不能为空"
    
    if not (1 <= max_results <= 10):
        max_results = 5
    
    search_results = await web_search_tool.search_web(query.strip(), max_results)
    
    if not search_results:
        return f"未找到关于 '{query}' 的搜索结果"
    
    # 格式化搜索结果
    formatted_results = [f"🔍 搜索查询: {query}\n"]
    for result in search_results:
        formatted_results.append(
            f"{result.rank}. **{result.title}**\n"
            f"   🔗 {result.url}\n"
            f"   📄 {result.snippet}\n"
            f"   📊 来源: {result.source}\n"
        )
    
    return "\n".join(formatted_results)


@mcp.tool()
async def extract_webpage(url: str) -> str:
    """
    提取指定网页的详细内容
    
    Args:
        url: 要提取内容的网页URL（必填）
    
    Returns:
        提取的网页内容，包括标题、摘要和完整内容
    """
    if not url or not url.strip():
        return "错误: URL不能为空"
    
    extracted_content = await web_search_tool.extract_content(url.strip())
    
    if not extracted_content:
        return f"无法提取网页内容: {url}"
    
    response = f"""📄 网页内容提取结果

🔗 URL: {extracted_content.url}
📝 标题: {extracted_content.title}
🔧 提取方法: {extracted_content.extraction_method}
📊 质量评分: {extracted_content.quality_score:.2f}
🎯 Token数量: {extracted_content.token_count}

📋 内容摘要:
{extracted_content.summary}

📖 完整内容:
{extracted_content.content}
"""
    
    return response


@mcp.tool()
async def search_and_extract(
    query: str, 
    max_results: int = 5, 
    extract_count: int = 3
) -> str:
    """
    搜索并自动提取网页内容，返回优化后的信息（推荐使用）
    
    Args:
        query: 搜索查询词（必填）
        max_results: 最大搜索结果数量，默认5，范围1-8
        extract_count: 提取详细内容的网页数量，默认3，范围1-5
    
    Returns:
        优化后的综合信息，适合LLM处理
    """
    if not query or not query.strip():
        return "错误: 搜索查询不能为空"
    
    # 参数验证
    max_results = max(1, min(max_results, 8))
    extract_count = max(1, min(extract_count, 5))
    
    # 执行搜索
    search_results = await web_search_tool.search_web(query.strip(), max_results)
    
    if not search_results:
        return f"未找到关于 '{query}' 的搜索结果"
    
    # 提取内容
    urls_to_extract = [result.url for result in search_results[:extract_count]]
    extracted_contents = []
    
    for url in urls_to_extract:
        try:
            content = await web_search_tool.extract_content(url)
            if content:
                extracted_contents.append(content)
        except Exception as e:
            logger.warning(f"提取内容失败 {url}: {e}")
    
    if not extracted_contents:
        # 如果没有提取到内容，返回搜索结果
        formatted_results = [f"🔍 搜索结果 (未能提取详细内容): {query}\n"]
        for result in search_results:
            formatted_results.append(
                f"{result.rank}. {result.title}\n   {result.snippet}\n   {result.url}\n"
            )
        return "\n".join(formatted_results)
    
    # 优化内容
    optimized_content = web_search_tool.optimize_content_for_llm(extracted_contents, query)
    
    return optimized_content



if __name__ == "__main__":
    mcp.run()
