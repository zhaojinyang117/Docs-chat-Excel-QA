"""
AI 文档聊天 & Excel QA 系统
Streamlit 主应用
"""
import streamlit as st
import pandas as pd
from typing import Optional

# 设置页面配置（必须在最前面）
st.set_page_config(
    page_title="AI 文档聊天 & Excel QA",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 导入自定义模块
import sys
sys.path.insert(0, ".")

from config import get_config, reset_config
from src.engines.doc_chat_engine import DocChatEngine
from src.engines.excel_qa_engine import ExcelQAEngine
from src.utils.auth import (
    init_auth_state, get_current_user, login_user, logout_user
)
from src.utils.logger import get_logger


# ============== 样式 ==============
st.markdown("""
<style>
    /* 主题色 */
    :root {
        --primary-color: #6366f1;
        --secondary-color: #8b5cf6;
        --background-color: #0f172a;
        --surface-color: #1e293b;
        --text-color: #e2e8f0;
    }
    
    /* 聊天消息样式 */
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    .user-message {
        background-color: #3b82f6;
        color: white;
    }
    
    .assistant-message {
        background-color: #1e293b;
        border: 1px solid #334155;
    }
    
    /* 来源卡片 */
    .source-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin-top: 0.5rem;
    }
    
    /* 文件信息 */
    .file-info {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        padding: 0.75rem 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    
    /* 统计数字 */
    .stat-number {
        font-size: 2rem;
        font-weight: bold;
        color: #6366f1;
    }
</style>
""", unsafe_allow_html=True)


# ============== 初始化 Session State ==============
def init_session_state():
    """初始化会话状态"""
    init_auth_state()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "doc_engine" not in st.session_state:
        st.session_state.doc_engine = None
    
    if "excel_engine" not in st.session_state:
        st.session_state.excel_engine = None
    
    if "current_file" not in st.session_state:
        st.session_state.current_file = None
    
    if "current_mode" not in st.session_state:
        st.session_state.current_mode = None  # "doc" or "excel"
    
    if "excel_preview" not in st.session_state:
        st.session_state.excel_preview = None


def get_file_type(filename: str) -> str:
    """根据文件名判断类型"""
    ext = filename.lower().split('.')[-1]
    if ext in ['pdf', 'docx', 'doc', 'txt']:
        return "doc"
    elif ext in ['xlsx', 'xls', 'csv']:
        return "excel"
    return "unknown"


# ============== 登录界面 ==============
def render_login():
    """渲染登录界面"""
    st.title("🔐 用户登录")
    
    st.markdown("""
    欢迎使用 **AI 文档聊天 & Excel QA 系统**！
    
    请输入用户名登录（新用户会自动注册）。
    """)
    
    with st.form("login_form"):
        username = st.text_input("用户名", placeholder="请输入用户名")
        submitted = st.form_submit_button("登录", use_container_width=True)
        
        if submitted:
            if username.strip():
                if login_user(username.strip()):
                    st.success(f"欢迎，{username}！")
                    st.rerun()
                else:
                    st.error("登录失败，请重试")
            else:
                st.warning("请输入用户名")


# ============== 侧边栏 ==============
def render_sidebar():
    """渲染侧边栏"""
    user = get_current_user()
    
    with st.sidebar:
        # 用户信息
        st.markdown(f"### 👤 {user['display_name']}")
        if st.button("退出登录", use_container_width=True):
            logout_user()
            st.session_state.messages = []
            st.session_state.doc_engine = None
            st.session_state.excel_engine = None
            st.session_state.current_file = None
            st.session_state.current_mode = None
            st.rerun()
        
        st.divider()
        
        # 文件上传
        st.markdown("### 📁 上传文件")
        uploaded_file = st.file_uploader(
            "选择文件",
            type=['pdf', 'docx', 'txt', 'xlsx', 'xls', 'csv'],
            help="支持 PDF、DOCX、TXT、Excel、CSV 文件"
        )
        
        if uploaded_file:
            file_type = get_file_type(uploaded_file.name)
            
            # 检查是否是新文件
            if (st.session_state.current_file is None or 
                st.session_state.current_file != uploaded_file.name):
                
                st.session_state.current_file = uploaded_file.name
                st.session_state.messages = []  # 清空聊天记录
                
                with st.spinner("正在处理文件..."):
                    try:
                        if file_type == "doc":
                            # 初始化文档引擎
                            engine = DocChatEngine(index_name=f"doc_{hash(uploaded_file.name)}")
                            count = engine.load_file(uploaded_file, uploaded_file.name)
                            st.session_state.doc_engine = engine
                            st.session_state.excel_engine = None
                            st.session_state.current_mode = "doc"
                            st.success(f"✅ 已加载 {count} 个文档块")
                            
                        elif file_type == "excel":
                            # 初始化 Excel 引擎
                            engine = ExcelQAEngine()
                            result = engine.load_file(uploaded_file, uploaded_file.name)
                            st.session_state.excel_engine = engine
                            st.session_state.doc_engine = None
                            st.session_state.current_mode = "excel"
                            st.session_state.excel_preview = engine.get_sheet_preview()
                            st.success(f"✅ 已加载 {result['sheet_count']} 个工作表")
                            
                        else:
                            st.error("不支持的文件类型")
                            
                    except Exception as e:
                        st.error(f"文件处理失败: {str(e)}")
                        st.session_state.current_file = None
        
        # 显示当前文件信息
        if st.session_state.current_file:
            st.divider()
            st.markdown("### 📄 当前文件")
            
            mode_icon = "📝" if st.session_state.current_mode == "doc" else "📊"
            st.markdown(f"""
            <div class="file-info">
                {mode_icon} <strong>{st.session_state.current_file}</strong>
            </div>
            """, unsafe_allow_html=True)
            
            # Excel 预览
            if st.session_state.current_mode == "excel" and st.session_state.excel_preview:
                preview = st.session_state.excel_preview
                st.caption(f"工作表: {preview.get('sheet_name', 'N/A')}")
                st.caption(f"行数: {preview.get('total_rows', 0)} | 列数: {preview.get('total_columns', 0)}")
            
            # 清空按钮
            if st.button("🗑️ 清空当前会话", use_container_width=True):
                st.session_state.messages = []
                if st.session_state.doc_engine:
                    st.session_state.doc_engine.clear_memory()
                if st.session_state.excel_engine:
                    st.session_state.excel_engine.clear_history()
                st.rerun()
        
        # 使用说明
        st.divider()
        with st.expander("💡 使用说明"):
            st.markdown("""
            **文档问答模式**
            - 支持 PDF、DOCX、TXT 文件
            - 可以询问文档内容相关问题
            - 系统会返回答案和来源段落
            
            **Excel 问答模式**
            - 支持 Excel、CSV 文件
            - 可以进行数据查询和计算
            - 例如："销售额最高的产品是什么？"
            """)


# ============== 文档聊天界面 ==============
def render_doc_chat():
    """渲染文档聊天界面"""
    engine = st.session_state.doc_engine
    
    if engine is None:
        st.info("📤 请在侧边栏上传文档文件开始对话")
        return
    
    # 显示聊天历史
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # 显示来源
            if msg["role"] == "assistant" and "sources" in msg:
                sources = msg["sources"]
                if sources:
                    with st.expander(f"📚 查看来源 ({len(sources)} 条)"):
                        for i, src in enumerate(sources):
                            st.markdown(f"""
                            **来源 {i+1}**: {src.get('source', '未知')} - 第 {src.get('page', 'N/A')} 页
                            
                            > {src.get('content', '')[:300]}...
                            """)
                            st.divider()
    
    # 聊天输入
    if prompt := st.chat_input("输入你的问题..."):
        # 添加用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 生成回答
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    response = engine.chat(prompt)
                    st.markdown(response.answer)
                    
                    # 显示来源
                    if response.sources:
                        with st.expander(f"📚 查看来源 ({len(response.sources)} 条)"):
                            for i, src in enumerate(response.sources):
                                st.markdown(f"""
                                **来源 {i+1}**: {src.get('source', '未知')} - 第 {src.get('page', 'N/A')} 页
                                
                                > {src.get('content', '')[:300]}...
                                """)
                                st.divider()
                    
                    # 添加到消息历史
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response.answer,
                        "sources": response.sources
                    })
                    
                    # 记录日志
                    user = get_current_user()
                    get_logger().log_doc_chat(
                        username=user["username"],
                        question=prompt,
                        answer=response.answer,
                        sources=response.sources,
                        file_name=st.session_state.current_file
                    )
                    
                except Exception as e:
                    st.error(f"生成回答时出错: {str(e)}")


# ============== Excel 问答界面 ==============
def render_excel_qa():
    """渲染 Excel 问答界面"""
    engine = st.session_state.excel_engine
    
    if engine is None:
        st.info("📤 请在侧边栏上传 Excel 或 CSV 文件开始对话")
        return
    
    # 数据预览
    if st.session_state.excel_preview:
        preview = st.session_state.excel_preview
        
        with st.expander("📊 数据预览", expanded=False):
            if "data" in preview and preview["data"]:
                df = pd.DataFrame(preview["data"])
                st.dataframe(df, use_container_width=True)
            
            st.caption(f"显示前 {len(preview.get('data', []))} 行，共 {preview.get('total_rows', 0)} 行")
    
    # 显示聊天历史
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg["content"]
            
            # 如果是 DataFrame，特殊处理
            if isinstance(content, pd.DataFrame):
                st.dataframe(content, use_container_width=True)
            else:
                st.markdown(str(content))
            
            # 显示定位信息
            if msg["role"] == "assistant" and "metadata" in msg:
                meta = msg["metadata"]
                if meta.get("sheet_name"):
                    st.caption(f"📍 来源: {meta.get('sheet_name', '')}")
    
    # 聊天输入
    if prompt := st.chat_input("输入你的问题，例如：销售额最高的产品是什么？"):
        # 添加用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 生成回答
        with st.chat_message("assistant"):
            with st.spinner("分析中..."):
                try:
                    response = engine.chat(prompt)
                    
                    # 根据返回类型显示
                    if response.answer_type == "dataframe":
                        st.dataframe(response.answer, use_container_width=True)
                        display_content = response.answer
                    elif response.answer_type == "chart":
                        st.image(response.answer)
                        display_content = f"[图表: {response.answer}]"
                    elif response.answer_type == "error":
                        st.error(response.answer)
                        display_content = response.answer
                    else:
                        st.markdown(str(response.answer))
                        display_content = str(response.answer)
                    
                    # 显示来源
                    if response.sheet_name:
                        st.caption(f"📍 来源: {response.sheet_name}")
                    
                    # 添加到消息历史
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": display_content,
                        "metadata": {
                            "sheet_name": response.sheet_name,
                            "answer_type": response.answer_type
                        }
                    })
                    
                    # 记录日志
                    user = get_current_user()
                    get_logger().log_excel_qa(
                        username=user["username"],
                        question=prompt,
                        answer=str(response.answer)[:1000],
                        sheet_name=response.sheet_name,
                        file_name=st.session_state.current_file,
                        generated_code=response.generated_code
                    )
                    
                except Exception as e:
                    st.error(f"处理问题时出错: {str(e)}")


# ============== 主界面 ==============
def render_main():
    """渲染主界面"""
    st.title("📚 AI 文档聊天 & Excel QA")
    
    if st.session_state.current_mode == "doc":
        st.markdown("### 📝 文档问答模式")
        render_doc_chat()
    elif st.session_state.current_mode == "excel":
        st.markdown("### 📊 Excel 问答模式")
        render_excel_qa()
    else:
        # 欢迎界面
        st.markdown("""
        ## 👋 欢迎使用
        
        这是一个基于 AI 的智能文档问答系统，支持：
        
        ### 📝 文档聊天
        - 上传 **PDF、DOCX、TXT** 文件
        - 与文档内容进行对话
        - 获取答案和来源引用
        
        ### 📊 Excel 问答
        - 上传 **Excel、CSV** 文件
        - 用自然语言查询数据
        - 支持数据计算和分析
        
        ---
        
        👈 **请在左侧上传文件开始使用**
        """)
        
        # 示例问题
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            #### 文档问答示例
            - "这份报告的主要结论是什么？"
            - "文档中提到了哪些关键数据？"
            - "请总结第三章的内容"
            """)
        
        with col2:
            st.markdown("""
            #### Excel 问答示例
            - "销售额最高的产品是什么？"
            - "2024年Q1的总收入是多少？"
            - "按地区统计销售数量"
            """)


# ============== 主函数 ==============
def main():
    """主函数"""
    init_session_state()
    
    # 检查登录状态
    user = get_current_user()
    
    if user is None:
        render_login()
    else:
        render_sidebar()
        render_main()


if __name__ == "__main__":
    main()

