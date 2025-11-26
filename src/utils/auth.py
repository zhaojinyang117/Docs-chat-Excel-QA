"""
简单用户认证模块
基于 Session State 的用户名登录
"""
import os
import json
import hashlib
from typing import Optional, Dict, List
from datetime import datetime

import sys
sys.path.insert(0, ".")
from config import get_config


class SimpleAuth:
    """简单用户认证"""
    
    def __init__(self, users_file: str = None):
        """
        初始化认证模块
        
        Args:
            users_file: 用户数据文件路径
        """
        config = get_config()
        self.users_file = users_file or os.path.join(config.data_dir, "users.json")
        self._ensure_file()
    
    def _ensure_file(self) -> None:
        """确保用户文件存在"""
        if not os.path.exists(self.users_file):
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            self._save_users({})
    
    def _load_users(self) -> Dict:
        """加载用户数据"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_users(self, users: Dict) -> None:
        """保存用户数据"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    
    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register(
        self,
        username: str,
        password: str = None,
        display_name: str = None
    ) -> bool:
        """
        注册用户
        
        Args:
            username: 用户名
            password: 密码（可选，简化版可不用）
            display_name: 显示名称
            
        Returns:
            是否注册成功
        """
        users = self._load_users()
        
        if username in users:
            return False
        
        users[username] = {
            "username": username,
            "password": self._hash_password(password) if password else None,
            "display_name": display_name or username,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        self._save_users(users)
        return True
    
    def login(
        self,
        username: str,
        password: str = None
    ) -> Optional[Dict]:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码（可选）
            
        Returns:
            用户信息，登录失败返回 None
        """
        users = self._load_users()
        
        # 如果用户不存在，自动注册（简化模式）
        if username not in users:
            self.register(username, password)
            users = self._load_users()
        
        user = users.get(username)
        if user is None:
            return None
        
        # 如果设置了密码，验证密码
        if user.get("password") and password:
            if self._hash_password(password) != user["password"]:
                return None
        
        # 更新最后登录时间
        user["last_login"] = datetime.now().isoformat()
        self._save_users(users)
        
        return {
            "username": user["username"],
            "display_name": user["display_name"],
            "last_login": user["last_login"]
        }
    
    def get_user(self, username: str) -> Optional[Dict]:
        """
        获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            用户信息
        """
        users = self._load_users()
        user = users.get(username)
        
        if user:
            return {
                "username": user["username"],
                "display_name": user["display_name"],
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login")
            }
        return None
    
    def update_user(
        self,
        username: str,
        display_name: str = None,
        password: str = None
    ) -> bool:
        """
        更新用户信息
        
        Args:
            username: 用户名
            display_name: 新的显示名称
            password: 新密码
            
        Returns:
            是否更新成功
        """
        users = self._load_users()
        
        if username not in users:
            return False
        
        if display_name:
            users[username]["display_name"] = display_name
        if password:
            users[username]["password"] = self._hash_password(password)
        
        self._save_users(users)
        return True
    
    def list_users(self) -> List[Dict]:
        """
        列出所有用户
        
        Returns:
            用户列表
        """
        users = self._load_users()
        return [
            {
                "username": u["username"],
                "display_name": u["display_name"],
                "created_at": u.get("created_at"),
                "last_login": u.get("last_login")
            }
            for u in users.values()
        ]
    
    def delete_user(self, username: str) -> bool:
        """
        删除用户
        
        Args:
            username: 用户名
            
        Returns:
            是否删除成功
        """
        users = self._load_users()
        
        if username not in users:
            return False
        
        del users[username]
        self._save_users(users)
        return True


# Streamlit 集成辅助函数
def init_auth_state():
    """初始化 Streamlit 认证状态"""
    import streamlit as st
    
    if "auth" not in st.session_state:
        st.session_state.auth = {
            "logged_in": False,
            "user": None
        }


def get_current_user() -> Optional[Dict]:
    """获取当前登录用户"""
    import streamlit as st
    
    init_auth_state()
    
    if st.session_state.auth["logged_in"]:
        return st.session_state.auth["user"]
    return None


def login_user(username: str, password: str = None) -> bool:
    """
    Streamlit 用户登录
    
    Args:
        username: 用户名
        password: 密码
        
    Returns:
        是否登录成功
    """
    import streamlit as st
    
    init_auth_state()
    
    auth = SimpleAuth()
    user = auth.login(username, password)
    
    if user:
        st.session_state.auth["logged_in"] = True
        st.session_state.auth["user"] = user
        return True
    return False


def logout_user() -> None:
    """Streamlit 用户登出"""
    import streamlit as st
    
    init_auth_state()
    
    st.session_state.auth["logged_in"] = False
    st.session_state.auth["user"] = None


def require_login(func):
    """
    装饰器：要求登录
    
    Usage:
        @require_login
        def my_page():
            st.write("只有登录后才能看到")
    """
    import streamlit as st
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        init_auth_state()
        
        if not st.session_state.auth["logged_in"]:
            st.warning("请先登录")
            return None
        return func(*args, **kwargs)
    
    return wrapper

