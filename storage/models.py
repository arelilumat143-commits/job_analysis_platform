# 城市招聘市场智能分析平台
"""
数据库模型定义 - SQLAlchemy ORM
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base

# 创建基类
Base = declarative_base()

class Job(Base):
    """
    职位信息数据模型
    
    Attributes:
        id: 主键ID
        title: 职位名称
        company: 公司名称
        salary_min: 最低薪资（单位：K/月）
        salary_max: 最高薪资（单位：K/月）
        city: 城市
        experience: 经验要求
        education: 学历要求
        skills: 技能要求列表（JSON格式存储）
        company_size: 公司规模
        company_type: 公司类型
        industry: 行业
        description: 职位描述
        url: 原始URL
        source: 数据来源（boss/zhilian/qiancheng）
        created_at: 创建时间
        updated_at: 更新时间
    """
    __tablename__ = 'jobs'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 基本信息
    title = Column(String(200), nullable=False, index=True, comment='职位名称')
    company = Column(String(200), nullable=False, index=True, comment='公司名称')
    
    # 薪资信息（单位：K/月，便于统一计算）
    salary_min = Column(Float, nullable=True, comment='最低薪资(K/月)')
    salary_max = Column(Float, nullable=True, comment='最高薪资(K/月)')
    
    # 基本要求
    city = Column(String(50), nullable=False, index=True, comment='城市')
    district = Column(String(50), nullable=True, comment='区/县')  # 与MySQL schema同步
    experience = Column(String(50), nullable=True, comment='经验要求')
    education = Column(String(50), nullable=True, comment='学历要求')
    
    # 技能要求（JSON格式存储列表）
    skills = Column(JSON, nullable=True, comment='技能要求列表')
    
    # 公司信息
    company_size = Column(String(50), nullable=True, comment='公司规模')
    company_type = Column(String(50), nullable=True, comment='公司类型')
    industry = Column(String(100), nullable=True, index=True, comment='行业')
    
    # 职位详情
    description = Column(Text, nullable=True, comment='职位描述')
    url = Column(String(500), nullable=True, comment='原始URL')
    
    # 来源信息
    source = Column(String(50), nullable=False, index=True, comment='数据来源')
    is_simulated = Column(Integer, nullable=False, default=0, comment='是否为模拟数据 0=真实 1=模拟')
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 索引
    __table_args__ = (
        Index('idx_city_source', 'city', 'source'),
        Index('idx_industry_source', 'industry', 'source'),
        Index('idx_salary_range', 'salary_min', 'salary_max'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}', city='{self.city}')>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'city': self.city,
            'district': self.district,
            'experience': self.experience,
            'education': self.education,
            'skills': self.skills,
            'company_size': self.company_size,
            'company_type': self.company_type,
            'industry': self.industry,
            'description': self.description,
            'url': self.url,
            'source': self.source,
            'is_simulated': self.is_simulated,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @property
    def salary_range(self):
        """薪资范围字符串"""
        if self.salary_min and self.salary_max:
            return f"{self.salary_min:.1f}K-{self.salary_max:.1f}K"
        return "薪资面议"
    
    @property
    def avg_salary(self):
        """平均薪资"""
        if self.salary_min and self.salary_max:
            return (self.salary_min + self.salary_max) / 2
        return None
