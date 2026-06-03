# 城市招聘市场智能分析平台
"""
缓存管理器 - 提供简单的内存缓存（模拟Redis接口）
"""

import time
from typing import Any, Optional, Dict
from collections import OrderedDict
import json
import logging

from config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    内存缓存管理器
    
    模拟Redis接口设计，支持TTL过期、LRU淘汰
    预留Redis连接配置，方便后续切换
    """
    
    _instance = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化缓存"""
        if self._initialized:
            return
            
        self._cache: OrderedDict = OrderedDict()
        self._ttl_cache: Dict[str, float] = {}  # 存储过期时间
        
        self._max_size = settings.redis.CACHE_MAX_SIZE
        self._default_ttl = settings.redis.CACHE_TTL
        
        # Redis配置（预留）
        self._redis_client = None
        self._redis_enabled = False
        
        # 尝试连接Redis（如已配置）
        self._try_connect_redis()
        
        self._initialized = True
        logger.info(f"缓存初始化完成，使用{'Redis' if self._redis_enabled else '内存'}")
    
    def _try_connect_redis(self):
        """尝试连接Redis（预留功能）"""
        if not settings.redis.REDIS_ENABLED:
            return
            
        try:
            import redis
            self._redis_client = redis.Redis(
                host=settings.redis.REDIS_HOST,
                port=settings.redis.REDIS_PORT,
                db=settings.redis.REDIS_DB,
                password=settings.redis.REDIS_PASSWORD,
                decode_responses=True
            )
            # 测试连接
            self._redis_client.ping()
            self._redis_enabled = True
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败，使用内存缓存: {e}")
            self._redis_client = None
            self._redis_enabled = False
    
    def _is_expired(self, key: str) -> bool:
        """检查key是否过期"""
        if key not in self._ttl_cache:
            return False
        return time.time() > self._ttl_cache[key]
    
    def _evict_if_needed(self):
        """LRU淘汰超出容量的key"""
        while len(self._cache) >= self._max_size:
            # 删除最旧的key
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            if oldest_key in self._ttl_cache:
                del self._ttl_cache[oldest_key]
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            Any: 缓存值，不存在或已过期返回None
        """
        # Redis优先
        if self._redis_enabled and self._redis_client:
            try:
                value = self._redis_client.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get失败: {e}")
        
        # 内存缓存
        if key in self._cache:
            if self._is_expired(key):
                self.delete(key)
                return None
            # 移到末尾（更新访问顺序）
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值
            
        Returns:
            bool: 是否设置成功
        """
        if ttl is None:
            ttl = self._default_ttl
        
        # Redis优先
        if self._redis_enabled and self._redis_client:
            try:
                self._redis_client.setex(
                    key, 
                    ttl, 
                    json.dumps(value, ensure_ascii=False)
                )
                return True
            except Exception as e:
                logger.warning(f"Redis set失败: {e}")
        
        # 内存缓存
        self._evict_if_needed()
        self._cache[key] = value
        self._cache.move_to_end(key)
        self._ttl_cache[key] = time.time() + ttl
        return True
    
    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否删除成功
        """
        # Redis优先
        if self._redis_enabled and self._redis_client:
            try:
                self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete失败: {e}")
        
        # 内存缓存
        if key in self._cache:
            del self._cache[key]
            if key in self._ttl_cache:
                del self._ttl_cache[key]
            return True
        return False
    
    def clear(self) -> bool:
        """
        清空所有缓存
        
        Returns:
            bool: 是否清空成功
        """
        # Redis优先
        if self._redis_enabled and self._redis_client:
            try:
                self._redis_client.flushdb()
            except Exception as e:
                logger.warning(f"Redis clear失败: {e}")
        
        # 内存缓存
        self._cache.clear()
        self._ttl_cache.clear()
        return True
    
    def exists(self, key: str) -> bool:
        """
        检查key是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否存在
        """
        # Redis优先
        if self._redis_enabled and self._redis_client:
            try:
                return bool(self._redis_client.exists(key))
            except Exception as e:
                logger.warning(f"Redis exists失败: {e}")
        
        # 内存缓存
        if key in self._cache:
            if self._is_expired(key):
                self.delete(key)
                return False
            return True
        return False
    
    def get_many(self, keys: list) -> Dict[str, Any]:
        """
        批量获取缓存
        
        Args:
            keys: 缓存键列表
            
        Returns:
            Dict[str, Any]: 存在的缓存键值对
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        批量设置缓存
        
        Args:
            data: 键值对字典
            ttl: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        for key, value in data.items():
            self.set(key, value, ttl)
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        # 清理过期key
        expired_keys = [k for k in self._cache.keys() if self._is_expired(k)]
        for key in expired_keys:
            self.delete(key)
        
        return {
            'type': 'redis' if self._redis_enabled else 'memory',
            'size': len(self._cache),
            'max_size': self._max_size,
            'redis_enabled': self._redis_enabled
        }


# 创建全局缓存管理器实例
cache_manager = CacheManager()
