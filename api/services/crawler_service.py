# 爬虫服务层
"""
爬虫任务管理服务
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from storage.database import db_manager


class CrawlerService:
    """
    爬虫服务
    
    提供爬虫任务管理和数据采集功能
    """
    
    # 可用的数据源配置
    AVAILABLE_SOURCES = [
        {
            "name": "BOSS直聘",
            "code": "boss",
            "enabled": True,
            "description": "BOSS直聘平台，提供互联网岗位为主"
        },
        {
            "name": "智联招聘",
            "code": "zhilian",
            "enabled": True,
            "description": "智联招聘平台，职位覆盖面广"
        },
        {
            "name": "前程无忧",
            "code": "qiancheng",
            "enabled": True,
            "description": "前程无忧51Job平台"
        },
        {
            "name": "实习僧",
            "code": "shixiseng",
            "enabled": True,
            "description": "实习僧平台，专注实习岗位"
        }
    ]
    
    def __init__(self):
        """初始化服务"""
        self.db = db_manager
    
    def get_available_sources(self) -> List[Dict[str, Any]]:
        """
        获取可用的数据源列表
        
        Returns:
            数据源列表
        """
        return self.AVAILABLE_SOURCES
    
    def run_crawler(
        self,
        source: str,
        city: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行爬虫任务
        
        Args:
            source: 数据源代码
            city: 城市（可选）
            keyword: 关键词（可选）
            
        Returns:
            爬虫执行结果
        """
        # 检查数据源是否有效
        valid_sources = [s["code"] for s in self.AVAILABLE_SOURCES if s["enabled"]]
        if source not in valid_sources:
            return {
                "success": False,
                "message": f"不支持的数据源: {source}",
                "added_count": 0
            }
        
        # 动态导入爬虫模块
        try:
            if source == "boss":
                from crawler.boss_crawler_v2 import BossCrawler
                crawler = BossCrawler()
            elif source == "zhilian":
                from crawler.zhilian_crawler_v2 import ZhilianCrawler
                crawler = ZhilianCrawler()
            elif source == "qiancheng":
                from crawler.qiancheng_crawler import QianChengCrawler
                crawler = QianChengCrawler()
            elif source == "shixiseng":
                from crawler.shixiseng_crawler_v2 import ShiXiSengCrawler
                crawler = ShiXiSengCrawler()
            else:
                return {
                    "success": False,
                    "message": f"未实现的爬虫: {source}",
                    "added_count": 0
                }
        except ImportError as e:
            return {
                "success": False,
                "message": f"爬虫模块导入失败: {str(e)}",
                "added_count": 0
            }
        
        try:
            # 执行爬虫
            # 注意：实际爬虫调用可能需要不同的参数
            jobs_data = []
            
            # 简化处理：如果爬虫支持批量采集
            if hasattr(crawler, 'collect_jobs'):
                jobs_data = crawler.collect_jobs(city=city, keyword=keyword)
            elif hasattr(crawler, 'run'):
                jobs_data = crawler.run(city=city, keyword=keyword)
            
            # 存储数据
            if jobs_data:
                added_count = self.db.add_jobs_batch(jobs_data)
                return {
                    "success": True,
                    "message": f"成功采集 {len(jobs_data)} 条数据，新增 {added_count} 条",
                    "collected_count": len(jobs_data),
                    "added_count": added_count
                }
            else:
                return {
                    "success": True,
                    "message": "未采集到新数据",
                    "collected_count": 0,
                    "added_count": 0
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"爬虫执行失败: {str(e)}",
                "added_count": 0
            }
    
    def get_total_jobs(self) -> int:
        """
        获取数据库中的职位总数
        
        Returns:
            职位总数
        """
        return self.db.count_jobs()
    
    def get_crawler_status(self) -> Dict[str, Any]:
        """
        获取爬虫状态
        
        Returns:
            爬虫状态信息
        """
        return {
            "total_jobs": self.get_total_jobs(),
            "available_sources": [s["code"] for s in self.AVAILABLE_SOURCES if s["enabled"]]
        }
