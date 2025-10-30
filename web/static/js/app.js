/**
 * FGO Agent 前端应用
 * 使用 WebSocket 与后端通信
 */

// ==================== 全局状态 ====================

const APP_STATE = {
    // WebSocket 连接
    ws: null,
    wsConnected: false,
    
    // 用户信息
    userId: null,
    username: null,
    
    // 当前会话
    currentSessionId: null,
    currentSessionName: null,
    
    // 会话列表
    sessions: [],
    
    // 消息列表
    messages: [],
    
    // 正在发送消息
    isSending: false,
    
    // 当前AI回复的消息ID
    currentAiMessageId: null,
};

// ==================== API 配置 ====================

const API_BASE_URL = window.location.origin;
const WS_BASE_URL = API_BASE_URL.replace('http', 'ws');

// ==================== DOM 元素 ====================

const DOM = {
    // 侧边栏
    username: document.getElementById('username'),
    userId: document.getElementById('user-id'),
    newSessionBtn: document.getElementById('newSessionBtn'),
    refreshSessionsBtn: document.getElementById('refreshSessionsBtn'),
    sessionsList: document.getElementById('sessionsList'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    
    // 聊天区域
    currentSessionName: document.getElementById('currentSessionName'),
    currentSessionId: document.getElementById('currentSessionId'),
    sessionCreated: document.getElementById('sessionCreated'),
    clearHistoryBtn: document.getElementById('clearHistoryBtn'),
    exportBtn: document.getElementById('exportBtn'),
    messagesContainer: document.getElementById('messagesContainer'),
    welcomeScreen: document.getElementById('welcomeScreen'),
    messagesList: document.getElementById('messagesList'),
    
    // 输入区域
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    
    // Toast
    toast: document.getElementById('toast'),
};

// ==================== 初始化 ====================

async function init() {
    console.log('🚀 初始化应用...');
    
    // 生成或获取用户ID
    APP_STATE.userId = getUserId();
    APP_STATE.username = getUsername();
    
    // 更新 UI
    DOM.username.textContent = APP_STATE.username;
    DOM.userId.textContent = `ID: ${APP_STATE.userId.substring(0, 8)}...`;
    
    // 绑定事件
    bindEvents();
    
    // 加载会话列表
    await loadSessions();
    
    // 如果没有会话，自动创建一个
    if (APP_STATE.sessions.length === 0) {
        await createNewSession();
    } else {
        // 选择第一个会话
        await selectSession(APP_STATE.sessions[0].session_id);
    }
    
    console.log('✅ 应用初始化完成');
}

// ==================== 用户管理 ====================

function getUserId() {
    let userId = localStorage.getItem('fgo_user_id');
    if (!userId) {
        userId = `user_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        localStorage.setItem('fgo_user_id', userId);
    }
    return userId;
}

function getUsername() {
    let username = localStorage.getItem('fgo_username');
    if (!username) {
        username = `玩家_${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
        localStorage.setItem('fgo_username', username);
    }
    return username;
}

// ==================== 会话管理 ====================

async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions/${APP_STATE.userId}?active_only=true`);
        if (!response.ok) throw new Error('加载会话列表失败');
        
        const sessions = await response.json();
        APP_STATE.sessions = sessions;
        
        // 渲染会话列表
        renderSessions();
        
        console.log(`📜 加载了 ${sessions.length} 个会话`);
    } catch (error) {
        console.error('❌ 加载会话失败:', error);
        showToast('加载会话列表失败', 'error');
    }
}

async function createNewSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: APP_STATE.userId,
                username: APP_STATE.username,
                session_name: `会话_${new Date().toLocaleString('zh-CN')}`,
            }),
        });
        
        if (!response.ok) throw new Error('创建会话失败');
        
        const session = await response.json();
        console.log('✅ 创建新会话:', session.session_id);
        
        // 重新加载会话列表
        await loadSessions();
        
        // 选择新创建的会话
        await selectSession(session.session_id);
        
        showToast('新会话已创建', 'success');
    } catch (error) {
        console.error('❌ 创建会话失败:', error);
        showToast('创建会话失败', 'error');
    }
}

async function selectSession(sessionId) {
    console.log(`📌 选择会话: ${sessionId}`);
    
    // 更新当前会话
    APP_STATE.currentSessionId = sessionId;
    
    // 查找会话信息
    const session = APP_STATE.sessions.find(s => s.session_id === sessionId);
    if (session) {
        APP_STATE.currentSessionName = session.session_name;
        DOM.currentSessionName.textContent = session.session_name;
        DOM.currentSessionId.textContent = `ID: ${sessionId.substring(0, 20)}...`;
        DOM.sessionCreated.textContent = `创建于 ${new Date(session.created_at).toLocaleString('zh-CN')}`;
    }
    
    // 更新 UI
    renderSessions();
    
    // 隐藏欢迎界面
    DOM.welcomeScreen.style.display = 'none';
    
    // 加载历史消息
    await loadHistory();
    
    // 连接 WebSocket
    connectWebSocket(sessionId);
}

function renderSessions() {
    DOM.sessionsList.innerHTML = '';
    
    if (APP_STATE.sessions.length === 0) {
        DOM.sessionsList.innerHTML = '<div style="text-align: center; color: var(--text-tertiary); font-size: 0.875rem; padding: 1rem;">暂无会话</div>';
        return;
    }
    
    APP_STATE.sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item';
        if (session.session_id === APP_STATE.currentSessionId) {
            item.classList.add('active');
        }
        
        item.innerHTML = `
            <div class="session-item-name">${session.session_name}</div>
            <div class="session-item-time">${new Date(session.created_at).toLocaleString('zh-CN')}</div>
        `;
        
        item.addEventListener('click', () => {
            selectSession(session.session_id);
        });
        
        DOM.sessionsList.appendChild(item);
    });
}

// ==================== WebSocket 连接 ====================

function connectWebSocket(sessionId) {
    // 关闭已有连接
    if (APP_STATE.ws) {
        APP_STATE.ws.close();
    }
    
    // 创建新连接
    const wsUrl = `${WS_BASE_URL}/ws/chat/${sessionId}`;
    console.log(`🔌 连接 WebSocket: ${wsUrl}`);
    
    APP_STATE.ws = new WebSocket(wsUrl);
    
    APP_STATE.ws.onopen = () => {
        console.log('✅ WebSocket 连接成功');
        APP_STATE.wsConnected = true;
        updateConnectionStatus(true);
    };
    
    APP_STATE.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    APP_STATE.ws.onerror = (error) => {
        console.error('❌ WebSocket 错误:', error);
        APP_STATE.wsConnected = false;
        updateConnectionStatus(false);
    };
    
    APP_STATE.ws.onclose = () => {
        console.log('🔌 WebSocket 连接关闭');
        APP_STATE.wsConnected = false;
        updateConnectionStatus(false);
        
        // 尝试重连
        setTimeout(() => {
            if (APP_STATE.currentSessionId) {
                console.log('🔄 尝试重新连接...');
                connectWebSocket(APP_STATE.currentSessionId);
            }
        }, 3000);
    };
}

function handleWebSocketMessage(data) {
    console.log('📨 收到消息:', data.type);
    
    switch (data.type) {
        case 'system':
            console.log('ℹ️ 系统消息:', data.content);
            break;
        
        case 'start':
            // AI 开始回复
            handleAiResponseStart();
            break;
        
        case 'token':
            // AI 回复的 token
            handleAiResponseToken(data.content);
            break;
        
        case 'end':
            // AI 回复结束
            handleAiResponseEnd(data.question_type);
            break;
        
        case 'error':
            // 错误消息
            handleAiResponseError(data.content);
            break;
        
        default:
            console.warn('⚠️ 未知消息类型:', data.type);
    }
}

function updateConnectionStatus(connected) {
    if (connected) {
        DOM.statusDot.classList.add('connected');
        DOM.statusText.textContent = '已连接';
    } else {
        DOM.statusDot.classList.remove('connected');
        DOM.statusText.textContent = '未连接';
    }
}

// ==================== 消息管理 ====================

async function loadHistory() {
    console.log('🔍 开始加载历史消息...');
    try {
        const response = await fetch(`${API_BASE_URL}/api/history/${APP_STATE.currentSessionId}?limit=50`);
        console.log('🔍 fetch 响应状态:', response.status);
        if (!response.ok) throw new Error('加载历史失败');
        
        const history = await response.json();
        console.log('🔍 解析后的历史数据:', history);
        console.log(`📜 加载了 ${history.length} 条历史消息`);
        
        // 清空消息列表
        DOM.messagesList.innerHTML = '';
        console.log('🔍 消息列表已清空');
        
        // 渲染历史消息
        console.log('🔍 开始遍历历史消息...');
        history.forEach((conv, index) => {
            console.log(`🔍 处理第 ${index + 1} 条消息:`, conv);
            console.log('渲染消息:', {
                role: conv.role,
                content: conv.content,
                contentLength: conv.content ? conv.content.length : 0
            });
            
            // 根据 role 判断是用户消息还是 AI 回复
            if (conv.role === 'user') {
                console.log('🔍 添加用户消息');
                appendMessage('user', conv.content, new Date(conv.created_at));
            } else if (conv.role === 'assistant') {
                console.log('🔍 添加AI消息');
                appendMessage('ai', conv.content, new Date(conv.created_at), conv.question_type);
            } else {
                console.warn('🔍 未知角色:', conv.role);
            }
        });
        console.log('🔍 历史消息遍历完成');
        
        // 滚动到底部
        scrollToBottom();
    } catch (error) {
        console.error('❌ 加载历史失败:', error);
        console.error('❌ 错误堆栈:', error.stack);
    }
}

function appendMessage(role, content, timestamp = new Date(), questionType = null) {
    console.log('appendMessage 调用:', { role, content, contentType: typeof content, contentValue: content });
    
    const messageId = `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    
    const message = document.createElement('div');
    message.className = `message ${role}`;
    message.id = messageId;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    const author = role === 'user' ? '你' : 'FGO Agent';
    
    let typeBadge = '';
    if (role === 'ai' && questionType) {
        const typeText = {
            'knowledge_base': '📚 知识库',
            'web_search': '🌐 网络搜索',
            'general': '💬 通用'
        }[questionType] || '💬 通用';
        
        typeBadge = `<span class="message-type-badge ${questionType}">${typeText}</span>`;
    }
    
    const escapedContent = escapeHtml(content);
    console.log('转义后的内容:', escapedContent);
    
    message.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-author">${author}</span>
                <span class="message-time">${formatTime(timestamp)}</span>
                ${typeBadge}
            </div>
            <div class="message-body">${escapedContent}</div>
        </div>
    `;
    
    DOM.messagesList.appendChild(message);
    console.log('消息已添加到 DOM, messageBody innerText:', message.querySelector('.message-body').innerText);
    scrollToBottom();
    
    return messageId;
}

function appendLoadingMessage() {
    const messageId = `msg_loading_${Date.now()}`;
    
    const message = document.createElement('div');
    message.className = 'message ai loading';
    message.id = messageId;
    
    message.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-author">FGO Agent</span>
                <span class="message-time">${formatTime(new Date())}</span>
            </div>
            <div class="message-body">
                <span class="typing-indicator">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </span>
            </div>
        </div>
    `;
    
    DOM.messagesList.appendChild(message);
    scrollToBottom();
    
    return messageId;
}

function handleAiResponseStart() {
    console.log('🤖 AI 开始回复');
    
    // 创建空消息用于流式更新
    const messageId = appendMessage('ai', '', new Date());
    APP_STATE.currentAiMessageId = messageId;
    console.log('🔍 创建的消息ID:', messageId);
    
    // 验证消息是否创建成功
    const msg = document.getElementById(messageId);
    console.log('🔍 消息元素是否存在:', !!msg);
    if (msg) {
        const body = msg.querySelector('.message-body');
        console.log('🔍 message-body 是否存在:', !!body);
        if (body) {
            console.log('🔍 message-body 初始内容:', body.textContent);
        }
    }
}

function handleAiResponseToken(token) {
    console.log('🔍 收到 token:', token, 'messageId:', APP_STATE.currentAiMessageId);
    
    if (!APP_STATE.currentAiMessageId) {
        console.warn('⚠️ currentAiMessageId 为空');
        return;
    }
    
    // 获取消息元素
    const message = document.getElementById(APP_STATE.currentAiMessageId);
    if (!message) {
        console.error('❌ 找不到消息元素:', APP_STATE.currentAiMessageId);
        return;
    }
    
    // 更新消息内容
    const messageBody = message.querySelector('.message-body');
    if (!messageBody) {
        console.error('❌ 找不到 message-body');
        return;
    }
    
    const currentContent = messageBody.textContent;
    messageBody.textContent = currentContent + token;
    console.log('🔍 更新后的内容长度:', messageBody.textContent.length);
    
    // 滚动到底部
    scrollToBottom();
}

function handleAiResponseEnd(questionType) {
    console.log('✅ AI 回复完成, 类型:', questionType);
    
    // 更新消息类型标签
    if (APP_STATE.currentAiMessageId && questionType) {
        const message = document.getElementById(APP_STATE.currentAiMessageId);
        if (message) {
            const header = message.querySelector('.message-header');
            const typeText = {
                'knowledge_base': '📚 知识库',
                'web_search': '🌐 网络搜索',
                'general': '💬 通用'
            }[questionType] || '💬 通用';
            
            const badge = document.createElement('span');
            badge.className = `message-type-badge ${questionType}`;
            badge.textContent = typeText;
            header.appendChild(badge);
        }
    }
    
    APP_STATE.currentAiMessageId = null;
    APP_STATE.isSending = false;
    
    // 启用输入
    DOM.messageInput.disabled = false;
    updateSendButton();
}

function handleAiResponseError(errorMessage) {
    console.error('❌ AI 回复错误:', errorMessage);
    
    // 如果有当前消息，更新为错误消息
    if (APP_STATE.currentAiMessageId) {
        const message = document.getElementById(APP_STATE.currentAiMessageId);
        if (message) {
            const messageBody = message.querySelector('.message-body');
            messageBody.textContent = `错误: ${errorMessage}`;
            messageBody.style.color = 'var(--error-color)';
        }
    } else {
        // 否则创建新的错误消息
        appendMessage('ai', `错误: ${errorMessage}`, new Date());
    }
    
    APP_STATE.currentAiMessageId = null;
    APP_STATE.isSending = false;
    
    // 启用输入
    DOM.messageInput.disabled = false;
    updateSendButton();
    
    showToast(errorMessage, 'error');
}

// ==================== 发送消息 ====================

function sendMessage() {
    const content = DOM.messageInput.value.trim();
    
    if (!content) return;
    if (!APP_STATE.wsConnected) {
        showToast('未连接到服务器', 'error');
        return;
    }
    if (APP_STATE.isSending) {
        showToast('请等待当前消息处理完成', 'error');
        return;
    }
    
    console.log('📤 发送消息:', content);
    
    // 添加用户消息到界面
    appendMessage('user', content, new Date());
    
    // 发送到服务器
    APP_STATE.ws.send(JSON.stringify({
        type: 'message',
        content: content,
    }));
    
    // 清空输入框
    DOM.messageInput.value = '';
    DOM.messageInput.style.height = 'auto';
    
    // 禁用输入
    APP_STATE.isSending = true;
    DOM.messageInput.disabled = true;
    updateSendButton();
}

// ==================== 事件绑定 ====================

function bindEvents() {
    // 新建会话
    DOM.newSessionBtn.addEventListener('click', createNewSession);
    
    // 刷新会话列表
    DOM.refreshSessionsBtn.addEventListener('click', loadSessions);
    
    // 清空历史
    DOM.clearHistoryBtn.addEventListener('click', () => {
        if (confirm('确定要清空当前会话的历史记录吗？')) {
            DOM.messagesList.innerHTML = '';
            showToast('历史记录已清空', 'success');
        }
    });
    
    // 导出对话
    DOM.exportBtn.addEventListener('click', exportConversation);
    
    // 输入框事件
    DOM.messageInput.addEventListener('input', () => {
        // 自动调整高度
        DOM.messageInput.style.height = 'auto';
        DOM.messageInput.style.height = DOM.messageInput.scrollHeight + 'px';
        
        // 更新发送按钮状态
        updateSendButton();
    });
    
    DOM.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // 发送按钮
    DOM.sendBtn.addEventListener('click', sendMessage);
    
    // 示例查询
    document.querySelectorAll('.example-query').forEach(btn => {
        btn.addEventListener('click', () => {
            DOM.messageInput.value = btn.textContent;
            updateSendButton();
            DOM.messageInput.focus();
        });
    });
}

function updateSendButton() {
    const hasContent = DOM.messageInput.value.trim().length > 0;
    const canSend = hasContent && APP_STATE.wsConnected && !APP_STATE.isSending;
    
    DOM.sendBtn.disabled = !canSend;
}

// ==================== 工具函数 ====================

function formatTime(date) {
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    
    return date.toLocaleString('zh-CN', {
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function escapeHtml(text) {
    if (!text) return '';  // 处理 undefined、null、空字符串
    const div = document.createElement('div');
    div.textContent = String(text);  // 确保转为字符串
    return div.innerHTML;
}

function scrollToBottom() {
    DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
}

function showToast(message, type = 'info') {
    DOM.toast.textContent = message;
    DOM.toast.className = `toast ${type}`;
    DOM.toast.classList.add('show');
    
    setTimeout(() => {
        DOM.toast.classList.remove('show');
    }, 3000);
}

function exportConversation() {
    const messages = Array.from(DOM.messagesList.querySelectorAll('.message')).map(msg => {
        const role = msg.classList.contains('user') ? 'User' : 'AI';
        const content = msg.querySelector('.message-body').textContent;
        const time = msg.querySelector('.message-time').textContent;
        return `[${time}] ${role}: ${content}`;
    }).join('\n\n');
    
    const blob = new Blob([messages], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `FGO_Agent_${APP_STATE.currentSessionName}_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('对话已导出', 'success');
}

// ==================== 启动应用 ====================

document.addEventListener('DOMContentLoaded', () => {
    init();
});

