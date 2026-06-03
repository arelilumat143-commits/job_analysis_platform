# 职位数据服务层
"""
职位数据查询和处理服务
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from storage.database import db_manager


class JobService:
    """
    职位数据服务
    
    提供职位数据的CRUD操作和查询功能
    """
    
    def __init__(self):
        """初始化服务"""
        self.db = db_manager
    
    def get_jobs_paginated(
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
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        分页查询职位
        
        Args:
            city: 城市筛选
            source: 数据来源
            industry: 行业
            keyword: 关键词
            experience: 经验要求
            education: 学历要求
            company_size: 公司规模
            company_type: 公司类型
            salary_min: 最低薪资
            salary_max: 最高薪资
            page: 页码
            page_size: 每页数量
            
        Returns:
            包含items和pagination的字典
        """
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 查询数据
        jobs = self.db.get_jobs(
            city=city,
            source=source,
            industry=industry,
            keyword=keyword,
            experience=experience,
            education=education,
            company_size=company_size,
            company_type=company_type,
            salary_min=salary_min,
            salary_max=salary_max,
            limit=page_size,
            offset=offset
        )
        
        # 统计总数
        total = self.db.count_jobs(
            city=city,
            source=source,
            industry=industry,
            keyword=keyword
        )
        
        # 计算总页数
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return {
            "items": jobs,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        }
    
    def search_jobs(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        全文搜索职位
        
        在职位名称、公司名称、职位描述中搜索
        """
        return self.get_jobs_paginated(keyword=keyword, page=page, page_size=page_size)
    
    def get_job_by_id(self, job_id: int) -> Optional[Dict]:
        """
        根据ID获取职位详情
        """
        return self.db.get_job_by_id(job_id)
    
    def get_job_stats(self) -> Dict[str, Any]:
        """
        获取职位统计概览
        """
        # 总数
        total = self.db.count_jobs()
        
        # 获取所有数据用于统计
        all_jobs = self.db.get_all_jobs()
        
        # 按城市统计
        city_stats = {}
        for job in all_jobs:
            city = job.get('city', '未知')
            if city not in city_stats:
                city_stats[city] = {"city": city, "count": 0}
            city_stats[city]["count"] += 1
        
        by_city = sorted(city_stats.values(), key=lambda x: x["count"], reverse=True)[:20]
        
        # 按行业统计
        industry_stats = {}
        for job in all_jobs:
            industry = job.get('industry') or '未知'
            if industry not in industry_stats:
                industry_stats[industry] = {"industry": industry, "count": 0}
            industry_stats[industry]["count"] += 1
        
        by_industry = sorted(industry_stats.values(), key=lambda x: x["count"], reverse=True)[:20]
        
        # 按来源统计
        source_stats = {}
        for job in all_jobs:
            source = job.get('source', '未知')
            if source not in source_stats:
                source_stats[source] = {"source": source, "count": 0}
            source_stats[source]["count"] += 1
        
        by_source = sorted(source_stats.values(), key=lambda x: x["count"], reverse=True)
        
        return {
            "total": total,
            "by_city": by_city,
            "by_industry": by_industry,
            "by_source": by_source
        }
    
    def get_distinct_values(self, field: str) -> List[str]:
        """
        获取指定字段的所有不重复值
        """
        return self.db.get_distinct_values(field)
    
    def delete_job(self, job_id: int) -> bool:
        """
        删除职位
        """
        return self.db.delete_job(job_id)
