"""内存缓存模块：用于缓存热点数据。"""
from typing import Any, Optional
from datetime import datetime, timedelta
import threading


class MemoryCache:
    """简单的内存缓存实现，支持过期时间。"""
    
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，如果过期则返回 None。"""
        with self._lock:
            if key not in self._cache:
                return None
            
            value, expire_at = self._cache[key]
            
            # 检查是否过期
            if expire_at and datetime.now() > expire_at:
                del self._cache[key]
                return None
            
            return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值。
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 表示永不过期
        """
        with self._lock:
            expire_at = None
            if ttl:
                expire_at = datetime.now() + timedelta(seconds=ttl)
            self._cache[key] = (value, expire_at)
    
    def delete(self, key: str):
        """删除缓存。"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        """清空所有缓存。"""
        with self._lock:
            self._cache.clear()


# 全局缓存实例
cache = MemoryCache()
