"""
FastMCP Web Search 工具测试文件

测试方式：
1. 直接测试工具函数（不启动 MCP 服务器）
2. 使用 MCP 客户端测试（启动服务器）
3. 使用 mcp CLI 工具测试
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量（在导入前设置）
os.environ.setdefault('MAX_SEARCH_RESULTS', '5')
os.environ.setdefault('MAX_CONTENT_TOKENS', '4000')
os.environ.setdefault('TIMEOUT_SECONDS', '20')
os.environ.setdefault('DEBUG', 'true')

from src.tools.web_search.web_search import WebSearchTool


# ============================================================================
# 测试 1: 直接测试工具类
# ============================================================================

async def test_web_search_tool():
    """测试 WebSearchTool 核心功能"""
    print("=" * 80)
    print("测试 1: WebSearchTool 核心功能测试")
    print("=" * 80)
    
    tool = WebSearchTool()
    
    try:
        # 测试搜索
        print("\n📍 测试搜索功能...")
        query = "FGO 奥博龙配队推荐"
        search_results = await tool.search_web(query, max_results=3)
        
        print(f"✅ 搜索成功，找到 {len(search_results)} 个结果:\n")
        for i, result in enumerate(search_results, 1):
            print(f"{i}. {result.title}")
            print(f"   URL: {result.url}")
            print(f"   摘要: {result.snippet[:100]}...\n")
        
        # 测试内容提取
        if search_results:
            print("\n📍 测试内容提取功能...")
            first_url = search_results[0].url
            print(f"正在提取: {first_url}")
            
            extracted = await tool.extract_content(first_url)
            
            if extracted:
                print(f"✅ 提取成功!")
                print(f"   标题: {extracted.title}")
                print(f"   方法: {extracted.extraction_method}")
                print(f"   质量: {extracted.quality_score:.2f}")
                print(f"   Token: {extracted.token_count}")
                print(f"   摘要: {extracted.summary[:150]}...")
            else:
                print("❌ 内容提取失败")
        
        # 测试内容优化
        print("\n📍 测试内容优化功能...")
        urls = [r.url for r in search_results[:2]]
        extracted_contents = []
        
        for url in urls:
            content = await tool.extract_content(url)
            if content:
                extracted_contents.append(content)
        
        if extracted_contents:
            optimized = tool.optimize_content_for_llm(extracted_contents, query)
            print(f"✅ 优化成功，优化后内容长度: {len(optimized)} 字符\n")
            print("优化后内容预览:")
            print("-" * 80)
            print(optimized[:500])
            print("..." if len(optimized) > 500 else "")
            print("-" * 80)
    
    finally:
        await tool.close()


# ============================================================================
# 测试 2: 测试 FastMCP 工具函数
# ============================================================================

async def test_mcp_tool_functions():
    """测试工具的完整功能（模拟 MCP 工具调用）"""
    print("\n" + "=" * 80)
    print("测试 2: 完整功能测试（搜索+提取+优化）")
    print("=" * 80)
    
    tool = WebSearchTool()
    
    try:
        # 测试完整流程：搜索 + 提取 + 优化
        print("\n📍 测试完整流程...")
        query = "Python FastMCP 教程"
        
        # 1. 搜索
        print(f"  步骤 1: 搜索 '{query}'")
        search_results = await tool.search_web(query, max_results=3)
        print(f"  ✅ 找到 {len(search_results)} 个结果")
        
        # 2. 提取内容
        print(f"  步骤 2: 提取前 2 个网页内容")
        extracted_contents = []
        for i, result in enumerate(search_results[:2], 1):
            print(f"     提取 {i}/{2}: {result.url[:50]}...")
            content = await tool.extract_content(result.url)
            if content:
                extracted_contents.append(content)
                print(f"     ✅ 成功 (质量: {content.quality_score:.2f})")
            else:
                print(f"     ❌ 失败")
        
        # 3. 优化内容
        if extracted_contents:
            print(f"  步骤 3: 优化内容")
            optimized = tool.optimize_content_for_llm(extracted_contents, query)
            print(f"  ✅ 优化完成，内容长度: {len(optimized)} 字符\n")
            print("优化后内容预览:")
            print("-" * 80)
            print(optimized[:500])
            print("..." if len(optimized) > 500 else "")
            print("-" * 80)
        else:
            print("  ❌ 没有成功提取任何内容")
    
    finally:
        await tool.close()


# ============================================================================
# 测试 3: 使用 MCP Inspector 测试（模拟客户端）
# ============================================================================

async def test_with_mcp_client():
    """使用 MCP 客户端库测试（需要安装 mcp）"""
    print("\n" + "=" * 80)
    print("测试 3: MCP 客户端测试")
    print("=" * 80)
    
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        # 配置服务器参数
        server_params = StdioServerParameters(
            command="python",
            args=[str(Path(__file__).parent / "web_search.py")],
            env=None
        )
        
        print("📍 启动 MCP 服务器...")
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 初始化
                await session.initialize()
                print("✅ MCP 服务器已初始化")
                
                # 列出可用工具
                tools = await session.list_tools()
                print(f"\n✅ 可用工具数量: {len(tools.tools)}")
                for tool in tools.tools:
                    print(f"   - {tool.name}: {tool.description}")
                
                # 调用工具
                print("\n📍 调用 search_and_extract 工具...")
                result = await session.call_tool(
                    "search_and_extract",
                    arguments={
                        "query": "FastMCP 使用教程",
                        "max_results": 3,
                        "extract_count": 2
                    }
                )
                
                print("✅ 工具调用成功!")
                for content in result.content:
                    print(content.text[:500])
                    print("..." if len(content.text) > 500 else "")
    
    except ImportError:
        print("⚠️ 未安装 mcp 客户端库，跳过此测试")
        print("   安装方法: pip install mcp")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


# ============================================================================
# 测试 4: 压力测试
# ============================================================================

async def test_concurrent_requests():
    """测试并发请求"""
    print("\n" + "=" * 80)
    print("测试 4: 并发请求测试")
    print("=" * 80)
    
    queries = [
        "FGO 英灵推荐",
        "Python 异步编程",
        "FastMCP 教程"
    ]
    
    print(f"📍 并发执行 {len(queries)} 个搜索...")
    
    # 创建独立的工具实例用于并发测试
    async def search_task(query: str):
        tool = WebSearchTool()
        try:
            results = await tool.search_web(query, max_results=2)
            return f"查询: {query}, 结果数: {len(results)}"
        except Exception as e:
            return e
        finally:
            await tool.close()
    
    tasks = [search_task(query) for query in queries]
    
    import time
    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start
    
    success_count = sum(1 for r in results if isinstance(r, str))
    
    print(f"✅ 完成! 耗时: {elapsed:.2f}秒")
    print(f"   成功: {success_count}/{len(queries)}")
    
    for i, (query, result) in enumerate(zip(queries, results), 1):
        if isinstance(result, str):
            print(f"\n{i}. {result}")
        else:
            print(f"\n{i}. {query}: 失败 - {result}")


# ============================================================================
# 测试 5: 错误处理测试
# ============================================================================

async def test_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 80)
    print("测试 5: 错误处理测试")
    print("=" * 80)
    
    tool = WebSearchTool()
    
    try:
        # 测试空查询
        print("\n📍 测试空查询...")
        results = await tool.search_web("", max_results=5)
        print(f"结果: 找到 {len(results)} 个结果（预期为空）")
        
        # 测试无效URL
        print("\n📍 测试无效URL...")
        result = await tool.extract_content("https://this-is-an-invalid-url-12345.com")
        if result:
            print(f"结果: {result.content[:100]}...")
        else:
            print(f"结果: None（预期失败）")
        
        # 测试正常查询
        print("\n📍 测试正常查询...")
        results = await tool.search_web("test", max_results=5)
        print(f"结果: 找到 {len(results)} 个结果")
    
    finally:
        await tool.close()


# ============================================================================
# 主测试函数
# ============================================================================

async def run_all_tests():
    """运行所有测试"""
    print("\n🚀 开始 FastMCP Web Search 工具测试\n")
    
    try:
        # 测试 1: 核心功能
        await test_web_search_tool()
        
        # 测试 2: MCP 工具函数
        await test_mcp_tool_functions()
        
        # 测试 3: MCP 客户端
        await test_with_mcp_client()
        
        # 测试 4: 并发测试
        await test_concurrent_requests()
        
        # 测试 5: 错误处理
        await test_error_handling()
        
        print("\n" + "=" * 80)
        print("✅ 所有测试完成!")
        print("=" * 80)
    
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# 使用说明
# ============================================================================

def print_usage():
    """打印使用说明"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                 FastMCP Web Search 工具测试指南                            ║
╚════════════════════════════════════════════════════════════════════════════╝

📋 测试方式：

1️⃣  直接运行测试脚本（推荐）
   python test_mcp.py

2️⃣  运行特定测试
   python -c "from test_mcp import test_web_search_tool; import asyncio; asyncio.run(test_web_search_tool())"

3️⃣  使用 MCP 服务器模式测试
   # 终端 1: 启动服务器
   python web_search.py
   
   # 终端 2: 使用 mcp CLI 测试
   mcp dev web_search:mcp

4️⃣  配置 Claude Desktop 测试
   编辑 Claude Desktop 配置文件：
   
   Windows: %APPDATA%/Claude/claude_desktop_config.json
   macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
   
   添加配置：
   {
     "mcpServers": {
       "web-search": {
         "command": "python",
         "args": ["D:/desktop/python++/langchain/FGO-agent/src/tools/web_search/web_search.py"]
       }
     }
   }

📝 环境变量配置（可选）：

   在运行前设置环境变量，或创建 .env 文件：
   
   MAX_SEARCH_RESULTS=5
   MAX_CONTENT_TOKENS=4000
   TIMEOUT_SECONDS=20
   DEBUG=true
   
   # Google API（可选）
   GOOGLE_API_KEY=your_key
   GOOGLE_CX=your_cx

📦 依赖安装：

   # 基础依赖
   pip install fastmcp httpx beautifulsoup4 readability-lxml tiktoken trafilatura newspaper3k python-dotenv
   
   # 测试依赖（可选）
   pip install mcp  # MCP 客户端库

🔍 测试内容：

   ✓ WebSearchTool 核心功能（搜索、提取、优化）
   ✓ FastMCP 工具函数
   ✓ MCP 客户端调用
   ✓ 并发请求
   ✓ 错误处理

💡 提示：

   - 首次运行可能较慢（需要下载网页）
   - 某些网站可能无法访问或提取
   - 使用 DEBUG=true 查看详细日志
   - 建议配置代理以提高成功率

════════════════════════════════════════════════════════════════════════════
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
    else:
        # 运行所有测试
        asyncio.run(run_all_tests())

