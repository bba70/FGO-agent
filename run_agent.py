"""
FGO Agent 主入口 - 命令行版本
提供简洁的命令行交互界面
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from src.agent.graph import create_game_character_graph
from src.memory.memory import MemoryManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 命令行模式固定配置
CLI_USER_ID = "cli_user"
CLI_USERNAME = "命令行用户"
MAX_TOKEN_LENGTH = 4000


class FGOAgent:
    """FGO Agent 主类 - 命令行简化版"""
    
    def __init__(self, restore_last_session: bool = False):
        """
        初始化 FGO Agent（命令行版本）
        
        Args:
            restore_last_session: 是否恢复上次会话（默认False，每次启动新会话）
            
        功能：
            1. 初始化 LangGraph
            2. 初始化 MemoryManager
            3. 确保固定用户存在
            4. 创建新会话或恢复上次会话
        """
        logger.info("🚀 初始化 FGO Agent...")
        
        # 1. 初始化 LangGraph
        self.graph = create_game_character_graph()
        logger.info("✅ LangGraph 初始化完成")
        
        # 2. 初始化 MemoryManager
        self.memory = MemoryManager(max_length=MAX_TOKEN_LENGTH)
        logger.info("✅ MemoryManager 初始化完成")
        
        # 3. 确保固定用户存在
        self.user_id = CLI_USER_ID
        user = self.memory.ensure_user_exists(self.user_id, CLI_USERNAME)
        logger.info(f"✅ 用户已就绪: {user.username} ({user.user_id})")
        
        # 4. 创建新会话或恢复上次会话
        if restore_last_session:
            # 尝试恢复最近的活跃会话
            sessions = self.memory.get_user_sessions(self.user_id, active_only=True)
            if sessions:
                self.session_id = sessions[0]['session_id']
                logger.info(f"✅ 恢复会话: {self.session_id}")
            else:
                # 没有活跃会话，创建新会话
                session_name = f"CLI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.session_id = self.memory.create_session(
                    self.user_id, 
                    CLI_USERNAME, 
                    session_name
                )
                logger.info(f"✅ 创建新会话: {self.session_id}")
        else:
            # 每次启动创建新会话
            session_name = f"CLI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.session_id = self.memory.create_session(
                self.user_id, 
                CLI_USERNAME, 
                session_name
            )
            logger.info(f"✅ 创建新会话: {self.session_id}")
        
        logger.info("🎉 FGO Agent 初始化完成！")
    
    # ==================== 核心对话功能 ====================
    
    async def chat_async(self, user_input: str) -> str:
        """
        异步处理用户输入（核心方法）
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            AI 回复文本
            
        流程：
            1. 从数据库加载历史对话（通过 MemoryManager）
            2. 添加当前用户输入到消息列表
            3. 调用 graph.ainvoke() 执行推理
            4. 从 graph 输出中提取 AI 回复
            5. 确定问题类型（knowledge_base/web_search/general）
            6. 计算 token 数量
            7. 保存对话到数据库
            8. 返回 AI 回复
        """
        try:
            # 1. 从数据库加载历史对话
            historical_messages = self.memory.build_langchain_message(self.session_id)
            logger.info(f"📚 加载历史消息: {len(historical_messages)} 条")
            
            # 2. 添加当前用户输入
            historical_messages.append(HumanMessage(content=user_input))
            
            # 3. 调用 graph 执行推理
            logger.info(f"🤔 处理用户输入: {user_input[:50]}...")
            result = await self.graph.ainvoke({"messages": historical_messages})
            
            # 4. 提取 AI 回复
            ai_response = self._extract_ai_response(result)
            
            # 5. 确定问题类型
            question_type = self._determine_question_type(result)
            
            # 6. 计算 token 数量
            token_count = self._calculate_tokens(user_input, ai_response)
            
            # 7. 保存对话到数据库
            save_success = self.memory.save_conversation_turn(
                session_id=self.session_id,
                query=user_input,
                response=ai_response,
                question_type=question_type,
                token_count=token_count
            )
            
            if save_success:
                logger.info(f"💾 对话已保存 - Session: {self.session_id}")
            else:
                logger.warning(f"⚠️  对话保存失败 - Session: {self.session_id}")
            
            # 8. 返回 AI 回复
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ 处理对话时发生错误: {e}", exc_info=True)
            return f"抱歉，处理您的请求时发生了错误：{str(e)}"
    
    def chat(self, user_input: str) -> str:
        """
        同步处理用户输入（兼容性方法）
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            AI 回复文本
            
        说明：
            内部使用 asyncio.run() 调用 chat_async()
            
        注意：
            - 不能在已有事件循环中调用此方法
            - 如果在 async 环境中，请直接使用 await chat_async()
        """
        try:
            # 检查是否已有运行中的事件循环
            loop = asyncio.get_running_loop()
            # 如果能获取到运行中的循环，说明在 async 环境中
            raise RuntimeError(
                "不能在 async 环境中调用 chat()！\n"
                "请使用: await agent.chat_async(user_input)"
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                # 没有运行中的事件循环，可以安全使用 asyncio.run()
                return asyncio.run(self.chat_async(user_input))
            else:
                # 其他 RuntimeError，重新抛出
                raise
    
    # ==================== 辅助功能 ====================
    
    def reset_session(self) -> str:
        """
        重置当前会话（清空历史，创建新会话）
        
        Returns:
            新会话ID
            
        功能：
            1. 停用当前会话
            2. 创建新会话
            3. 更新 self.session_id
        """
        logger.info(f"🔄 重置会话: {self.session_id}")
        
        try:
            # 1. 停用当前会话
            old_session_id = self.session_id
            self.memory.deactivate_session(old_session_id)
            logger.info(f"✅ 已停用旧会话: {old_session_id}")
            
            # 2. 创建新会话
            session_name = f"CLI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            new_session_id = self.memory.create_session(
                self.user_id, 
                CLI_USERNAME, 
                session_name
            )
            logger.info(f"✅ 创建新会话: {new_session_id}")
            
            # 3. 更新 self.session_id
            self.session_id = new_session_id
            
            return new_session_id
            
        except Exception as e:
            logger.error(f"❌ 重置会话失败: {e}")
            raise
    
    # ==================== 查询历史功能（可选）====================
    
    def show_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        显示最近的对话历史
        
        Args:
            limit: 显示的对话数量（默认10条）
            
        Returns:
            对话列表，每个元素包含：query, response, question_type, created_at
            
        功能：
            委托给 self.memory.get_conversation_history()
        """
        try:
            # 获取对话历史（Conversation 对象列表）
            conversations = self.memory.get_conversation_history(
                session_id=self.session_id,
                limit=limit
            )
            
            # 转换为字典列表
            history = []
            for conv in conversations:
                history.append({
                    'turn_number': conv.turn_number,
                    'query': conv.query,
                    'response': conv.response,
                    'question_type': conv.question_type,
                    'created_at': conv.created_at,
                    'token_count': conv.token_count
                })
            
            logger.info(f"📜 获取历史记录: {len(history)} 条")
            return history
            
        except Exception as e:
            logger.error(f"❌ 获取历史记录失败: {e}")
            return []
    
    # ==================== 工具方法 ====================
    
    def _extract_ai_response(self, graph_output: Dict[str, Any]) -> str:
        """
        从 graph 输出中提取 AI 回复
        
        Args:
            graph_output: graph.ainvoke() 的返回值
            
        Returns:
            AI 回复文本
            
        逻辑：
            从 graph_output["messages"] 的最后一条 AIMessage 中提取 content
        """
        messages = graph_output.get("messages", [])
        
        # 从后往前找第一条 AIMessage
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return message.content
        
        # 如果没找到，返回默认消息
        logger.warning("⚠️ 未在 graph 输出中找到 AIMessage")
        return "抱歉，我现在无法回答您的问题。"
    
    def _determine_question_type(self, graph_output: Dict[str, Any]) -> str:
        """
        从 graph 输出中确定问题类型
        
        Args:
            graph_output: graph.ainvoke() 的返回值
            
        Returns:
            问题类型：knowledge_base / web_search / general
            
        逻辑：
            根据 graph_output 中的 classification 或其他标志位判断
        """
        # 检查 classification 字段
        classification = graph_output.get("classification", "")
        
        if classification == "knowledge_base":
            return "knowledge_base"
        elif classification == "web_search":
            return "web_search"
        elif classification == "end":
            return "general"
        
        # 如果没有 classification，尝试根据其他标志位判断
        if graph_output.get("retrieved_docs"):
            return "knowledge_base"
        
        # 默认为 general
        return "general"
    
    def _calculate_tokens(self, user_input: str, ai_response: str) -> int:
        """
        计算本轮对话的 token 数量
        
        Args:
            user_input: 用户输入
            ai_response: AI 回复
            
        Returns:
            token 总数（使用 tiktoken 精确计算）
        """
        # 使用 MemoryManager 中的精确 token 计算方法
        combined_text = user_input + ai_response
        return self.memory.token_calculate(combined_text)


# ==================== 交互式命令行界面 ====================

class InteractiveCLI:
    """简洁的命令行交互界面"""
    
    def __init__(self, agent: FGOAgent):
        """
        初始化 CLI
        
        Args:
            agent: FGOAgent 实例
        """
        self.agent = agent
    
    def run(self):
        """
        运行交互式界面
        
        流程：
            1. 显示欢迎横幅（带 session 信息）
            2. 主循环：
               - 👤 读取用户输入（带提示符）
               - 处理命令（/help, /history, /reset, /exit）
               - 或调用 agent.chat() 对话
               - 🤖 美化显示 AI 回复
            3. Ctrl+C 或 /exit 优雅退出
            
        美化特性：
            - 彩色输出（emoji + 图标）
            - 对话分隔线
            - 状态提示（思考中...）
            - 错误友好提示
        """
        # 1. 显示欢迎信息
        self._display_welcome()
        
        # 2. 主循环
        try:
            while True:
                try:
                    # 读取用户输入
                    user_input = input("\n👤 You: ").strip()
                    
                    # 空输入，跳过
                    if not user_input:
                        continue
                    
                    # 处理命令
                    if self._handle_command(user_input):
                        continue
                    
                    # 普通对话
                    self._print_separator("-", 60)
                    print("⏳ Agent 思考中...")
                    
                    try:
                        response = self.agent.chat(user_input)
                        self._print_agent_response(response)
                    except Exception as e:
                        self._print_error(f"对话失败: {e}")
                        logger.error(f"对话失败: {e}", exc_info=True)
                    
                    self._print_separator("-", 60)
                    
                except KeyboardInterrupt:
                    print("\n")
                    self._print_info("检测到 Ctrl+C，输入 /exit 退出")
                    continue
                    
        except EOFError:
            # 用户按了 Ctrl+D
            print("\n")
            self._print_info("再见！")
        except Exception as e:
            self._print_error(f"发生错误: {e}")
            logger.error(f"CLI 运行错误: {e}", exc_info=True)
    
    def _handle_command(self, user_input: str) -> bool:
        """
        处理特殊命令（返回True表示已处理，False表示普通对话）
        
        支持的命令：
            /help - 显示帮助
            /history [n] - 显示最近n条历史（默认10）
            /reset - 重置会话（清空历史）
            /exit 或 /quit - 退出
        
        Args:
            user_input: 用户输入
            
        Returns:
            是否是命令（True=已处理，False=普通对话）
        """
        # 不是命令
        if not user_input.startswith('/'):
            return False
        
        # 解析命令和参数
        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # /help - 显示帮助
        if command == '/help':
            self._display_help()
            return True
        
        # /history [n] - 显示历史
        elif command == '/history':
            limit = int(args[0]) if args and args[0].isdigit() else 10
            history = self.agent.show_history(limit=limit)
            self._display_history(history)
            return True
        
        # /reset - 重置会话
        elif command == '/reset':
            try:
                new_session_id = self.agent.reset_session()
                self._print_success(f"会话已重置！新会话ID: {new_session_id[:20]}...")
            except Exception as e:
                self._print_error(f"重置失败: {e}")
            return True
        
        # /exit 或 /quit - 退出
        elif command in ['/exit', '/quit']:
            self._print_separator("=", 60)
            print("\n👋 感谢使用 FGO Agent！再见！\n")
            self._print_separator("=", 60)
            exit(0)
        
        # 未知命令
        else:
            self._print_error(f"未知命令: {command}")
            self._print_info("输入 /help 查看可用命令")
            return True
    
    def _display_welcome(self):
        """
        显示欢迎信息和使用提示
        
        美化元素：
            - 使用分隔线和边框
            - 使用 emoji 图标
            - 显示 session ID 和时间
            - 彩色文本（如果支持）
        """
        self._print_separator("=", 60)
        print("🎮 FGO Agent - Fate/Grand Order 智能助手 v1.0")
        self._print_separator("=", 60)
        print(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔑 Session ID: {self.agent.session_id}")
        print(f"👤 User ID: {self.agent.user_id}")
        self._print_separator("-", 60)
        print("💡 提示：")
        print("  - 直接输入问题开始对话")
        print("  - 输入 /help 查看可用命令")
        print("  - 输入 /exit 或按 Ctrl+D 退出")
        self._print_separator("=", 60)
    
    def _display_help(self):
        """
        显示帮助信息
        
        显示内容：
            - 可用命令列表（带图标）
            - 使用示例
            - 快捷键提示
        """
        self._print_separator("=", 60)
        print("📖 可用命令列表")
        self._print_separator("=", 60)
        print()
        print("  /help              - 📖 显示此帮助信息")
        print("  /history [n]       - 📜 显示最近 n 条历史记录（默认10条）")
        print("  /reset             - 🔄 重置会话（清空历史，开始新对话）")
        print("  /exit 或 /quit     - 👋 退出程序")
        print()
        self._print_separator("-", 60)
        print("💡 使用技巧：")
        print("  - 直接输入问题即可对话")
        print("  - Ctrl+C 不会退出，只会中断当前操作")
        print("  - Ctrl+D 或 /exit 可以优雅退出")
        self._print_separator("=", 60)
    
    def _display_history(self, conversations: List[Dict[str, Any]]):
        """
        格式化显示对话历史
        
        Args:
            conversations: 对话列表
            
        美化元素：
            - 👤 用户图标 + 🤖 AI图标
            - 时间戳显示
            - 问题类型标签（knowledge_base/web_search/general）
            - 分隔线区分不同对话
        """
        if not conversations:
            self._print_info("暂无历史记录")
            return
        
        self._print_separator("=", 60)
        print(f"📜 最近 {len(conversations)} 条对话历史")
        self._print_separator("=", 60)
        
        # 问题类型图标映射
        type_icons = {
            'knowledge_base': '📚',
            'web_search': '🌐',
            'general': '💬'
        }
        
        for i, conv in enumerate(conversations, 1):
            # 获取图标
            icon = type_icons.get(conv.get('question_type', 'general'), '💬')
            time_str = conv['created_at'].strftime('%Y-%m-%d %H:%M:%S') if conv.get('created_at') else 'Unknown'
            
            print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"[{i}] Turn {conv['turn_number']} | {icon} {conv.get('question_type', 'general')} | {time_str}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"👤 You: {conv['query']}")
            print(f"\n🤖 Agent: {conv['response'][:200]}{'...' if len(conv['response']) > 200 else ''}")
        
        self._print_separator("=", 60)
    
    def _print_user_input(self, text: str):
        """
        格式化显示用户输入
        
        格式：👤 You: {text}
        """
        print(f"\n👤 You: {text}")
    
    def _print_agent_response(self, text: str):
        """
        格式化显示 Agent 回复
        
        格式：🤖 Agent: {text}
        """
        print(f"\n🤖 Agent: {text}")
    
    def _print_separator(self, char: str = "=", length: int = 60):
        """打印分隔线"""
        print(char * length)
    
    def _print_info(self, text: str):
        """打印信息（带 ℹ️ 图标）"""
        print(f"ℹ️  {text}")
    
    def _print_error(self, text: str):
        """打印错误（带 ❌ 图标）"""
        print(f"❌ {text}")
    
    def _print_success(self, text: str):
        """打印成功（带 ✅ 图标）"""
        print(f"✅ {text}")


# ==================== 单次查询模式（用于测试/API）====================

def run_single_query(query: str, restore_session: bool = False) -> str:
    """
    单次查询模式（不进入交互界面）
    
    Args:
        query: 查询内容
        restore_session: 是否恢复上次会话（默认False）
        
    Returns:
        AI 回复
        
    使用场景：
        - 快速测试
        - 脚本集成
    """
    try:
        # 初始化 Agent
        agent = FGOAgent(restore_last_session=restore_session)
        
        # 执行查询
        print(f"👤 Query: {query}")
        print("⏳ Processing...")
        response = agent.chat(query)
        print(f"\n🤖 Response: {response}")
        
        return response
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Single query failed: {e}", exc_info=True)
        return f"Error: {e}"


# ==================== 主入口 ====================

def main():
    """
    主入口函数
    
    功能：
        1. 解析命令行参数（可选）
           - 无参数：交互模式
           - -q "查询内容"：单次查询模式
           - --restore：恢复上次会话
        2. 初始化 FGOAgent
        3. 启动对应模式
        
    示例：
        python run_agent.py                    # 交互模式（新会话）
        python run_agent.py --restore         # 交互模式（恢复上次会话）
        python run_agent.py -q "阿尔托莉雅的宝具是什么"  # 单次查询
    """
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="FGO Agent - Fate/Grand Order 智能助手",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '-q', '--query',
        type=str,
        help='单次查询模式：直接提问并退出'
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='恢复上次会话（默认每次启动新会话）'
    )
    
    args = parser.parse_args()
    
    try:
        # 单次查询模式
        if args.query:
            run_single_query(args.query, restore_session=args.restore)
        
        # 交互模式
        else:
            agent = FGOAgent(restore_last_session=args.restore)
            cli = InteractiveCLI(agent)
            cli.run()
            
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    except Exception as e:
        print(f"\n❌ 程序异常退出: {e}")
        logger.error(f"Main function error: {e}", exc_info=True)


if __name__ == "__main__":
    main()

