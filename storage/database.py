# 城市招聘市场智能分析平台
"""
数据库管理器 - 提供CRUD操作
"""

from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from datetime import datetime
import logging

from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from config import settings
from .models import Base, Job

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    数据库管理器
    
    提供完整的CRUD操作，支持批量插入、条件查询等功能
    """
    
    _instance = None
    _engine = None
    _session_factory = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化数据库连接"""
        if self._initialized:
            return
            
        db_url = settings.get_db_url()
        logger.info(f"初始化数据库连接: {db_url}")
        
        # 创建引擎
        if 'sqlite' in db_url:
            # SQLite特殊配置
            self._engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            self._engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                echo=False
            )
        
        # 创建会话工厂
        self._session_factory = sessionmaker(bind=self._engine)
        
        # 创建表
        self._create_tables()
        
        self._initialized = True
        logger.info("数据库初始化完成")
    
    def _create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(self._engine)
        logger.info("数据库表创建完成")
    
    @contextmanager
    def get_session(self) -> Session:
        """
        获取数据库会话的上下文管理器
        
        Yields:
            Session: 数据库会话
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()
    
    def add_job(self, job_data: Dict[str, Any]) -> Optional[Job]:
        """
        添加单条职位数据
        
        Args:
            job_data: 职位数据字典
            
        Returns:
            Job: 创建的职位对象
        """
        with self.get_session() as session:
            # 检查是否已存在（根据URL去重）
            if job_data.get('url'):
                exists = session.query(Job).filter(Job.url == job_data['url']).first()
                if exists:
                    logger.debug(f"职位已存在，跳过: {job_data.get('title')}")
                    return None
            
            job = Job(**job_data)
            session.add(job)
            session.flush()
            job_id = job.id
            return job
    
    def add_jobs_batch(self, jobs_data: List[Dict[str, Any]]) -> int:
        """
        批量添加职位数据
        
        Args:
            jobs_data: 职位数据列表
            
        Returns:
            int: 实际插入的数量
        """
        if not jobs_data:
            return 0
        
        added_count = 0
        with self.get_session() as session:
            # 获取已存在的URL集合
            urls = {job_data.get('url') for job_data in jobs_data if job_data.get('url')}
            existing_urls = set()
            if urls:
                existing = session.query(Job.url).filter(Job.url.in_(urls)).all()
                existing_urls = {row[0] for row in existing}
            
            # 过滤并添加新数据
            new_jobs = []
            for job_data in jobs_data:
                if job_data.get('url') and job_data['url'] in existing_urls:
                    continue
                new_jobs.append(Job(**job_data))
                existing_urls.add(job_data.get('url'))
            
            if new_jobs:
                session.bulk_save_objects(new_jobs)
                added_count = len(new_jobs)
        
        logger.info(f"批量插入完成，新增 {added_count} 条数据")
        return added_count
    
    def get_job_by_id(self, job_id: int) -> Optional[Dict]:
        """
        根据ID获取职位
        
        Args:
            job_id: 职位ID
            
        Returns:
            Dict: 职位字典
        """
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                # 在session内转换为字典，避免detached问题
                return {
                    'id': job.id,
                    'title': job.title,
                    'company': job.company,
                    'salary_min': job.salary_min,
                    'salary_max': job.salary_max,
                    'city': job.city,
                    'experience': job.experience,
                    'education': job.education,
                    'skills': job.skills,
                    'company_size': job.company_size,
                    'company_type': job.company_type,
                    'industry': job.industry,
                    'description': job.description,
                    'url': job.url,
                    'source': job.source,
                    'created_at': job.created_at.isoformat() if job.created_at else None,
                    'updated_at': job.updated_at.isoformat() if job.updated_at else None,
                }
            return None
    
    def get_jobs(
        self,
        city: Optional[str] = None,
        source: Optional[str] = None,
        industry: Optional[str] = None,
        keyword: Optional[str] = None,
        experience: Optional[str] = None,
        education: Optional[str] = None,
        company_size: Optional[str] = None,
        company_type: Optional[str] = None,
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        条件查询职位列表
        
        Args:
            city: 城市
            source: 数据来源
            industry: 行业
            keyword: 关键词（搜索职位名称和公司名称）
            experience: 经验要求
            education: 学历要求
            company_size: 公司规模
            company_type: 公司类型
            salary_min: 最低薪资
            salary_max: 最高薪资
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List[Dict]: 职位字典列表
        """
        with self.get_session() as session:
            query = session.query(Job)
            
            # 动态添加过滤条件
            if city:
                query = query.filter(Job.city == city)
            if source:
                query = query.filter(Job.source == source)
            if industry:
                query = query.filter(Job.industry == industry)
            if keyword:
                search = f"%{keyword}%"
                query = query.filter(
                    or_(
                        Job.title.like(search),
                        Job.company.like(search)
                    )
                )
            if experience:
                query = query.filter(Job.experience == experience)
            if education:
                query = query.filter(Job.education == education)
            if company_size:
                query = query.filter(Job.company_size == company_size)
            if company_type:
                query = query.filter(Job.company_type == company_type)
            if salary_min:
                query = query.filter(Job.salary_max >= salary_min)
            if salary_max:
                query = query.filter(Job.salary_min <= salary_max)
            
            # 按创建时间倒序
            query = query.order_by(Job.created_at.desc())
            
            # 分页
            jobs = query.offset(offset).limit(limit).all()
            return [job.to_dict() for job in jobs]
    
    def get_all_jobs(self) -> List[Dict]:
        """
        获取所有职位
        
        Returns:
            List[Dict]: 所有职位字典列表
        """
        with self.get_session() as session:
            jobs = session.query(Job).order_by(Job.created_at.desc()).all()
            return [job.to_dict() for job in jobs]
    
    def count_jobs(
        self,
        city: Optional[str] = None,
        source: Optional[str] = None,
        industry: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> int:
        """
        统计职位数量
        
        Returns:
            int: 职位数量
        """
        with self.get_session() as session:
            query = session.query(func.count(Job.id))
            
            if city:
                query = query.filter(Job.city == city)
            if source:
                query = query.filter(Job.source == source)
            if industry:
                query = query.filter(Job.industry == industry)
            if keyword:
                search = f"%{keyword}%"
                query = query.filter(
                    or_(
                        Job.title.like(search),
                        Job.company.like(search)
                    )
                )
            
            return query.scalar()
    
    def get_distinct_values(self, field: str) -> List[str]:
        """
        获取指定字段的所有不重复值
        
        Args:
            field: 字段名
            
        Returns:
            List[str]: 不重复值列表
        """
        with self.get_session() as session:
            if hasattr(Job, field):
                values = session.query(getattr(Job, field)).distinct().all()
                return [v[0] for v in values if v[0]]
        return []
    
    def delete_job(self, job_id: int) -> bool:
        """
        删除职位
        
        Args:
            job_id: 职位ID
            
        Returns:
            bool: 是否删除成功
        """
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                session.delete(job)
                return True
        return False
    
    def clear_all_jobs(self) -> int:
        """
        清空所有职位数据
        
        Returns:
            int: 删除的数量
        """
        with self.get_session() as session:
            count = session.query(Job).count()
            session.query(Job).delete()
            return count
    
    def update_job(self, job_id: int, update_data: Dict[str, Any]) -> Optional[Job]:
        """
        更新职位数据
        
        Args:
            job_id: 职位ID
            update_data: 更新数据
            
        Returns:
            Job: 更新后的职位
        """
        with self.get_session() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                for key, value in update_data.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                job.updated_at = datetime.now()
                session.flush()
                return job
        return None


# 创建全局数据库管理器实例
db_manager = DatabaseManager()
