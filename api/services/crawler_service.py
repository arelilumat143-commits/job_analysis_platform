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
    
    # 可用的数据源配置（仅智联已实现，其余待开发）
    AVAILABLE_SOURCES = [
        {
            "name": "智联招聘",
            "code": "zhilian",
            "enabled": True,
            "description": "智联招聘平台，职位覆盖面广"
        },
        {
            "name": "BOSS直聘",
            "code": "boss",
            "enabled": False,
            "description": "BOSS直聘平台（爬虫待开发）"
        },
        {
            "name": "前程无忧",
            "code": "qiancheng",
            "enabled": False,
            "description": "前程无忧51Job平台（爬虫待开发）"
        },
        {
            "name": "实习僧",
            "code": "shixiseng",
            "enabled": False,
            "description": "实习僧平台（爬虫待开发）"
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
            if source == "zhilian":
                # 使用真实的智联爬虫模块
                from crawler.zhilian_crawler import ZhilianCrawler
                # ZhilianCrawler 内部已通过 db_manager.add_job 直接入库
                # run() 返回 stats 字典，包含 added/skipped/failed 等
                crawler = ZhilianCrawler(
                    keyword=keyword or "Python",
                    city=city or "北京",
                    max_pages=1,  # 默认爬1页，避免等待过久
                    headless=True,
                    fetch_detail=False,
                )
                stats = crawler.run()
                return {
                    "success": True,
                    "message": (
                        f"爬取完成 | 找到 {stats.get('jobs_found', 0)} 条 "
                        f"| 新增 {stats.get('added', 0)} 条 "
                        f"| 跳过 {stats.get('skipped', 0)} 条 "
                        f"| 失败 {stats.get('failed', 0)} 条"
                    ),
                    "added_count": stats.get("added", 0),
                    "collected_count": stats.get("jobs_found", 0),
                    "skipped_count": stats.get("skipped", 0),
                    "failed_count": stats.get("failed", 0),
                }
            else:
                return {
                    "success": False,
                    "message": f"爬虫未实现: {source}（当前仅支持智联招聘）",
                    "added_count": 0
                }
        except ImportError as e:
            return {
                "success": False,
                "message": f"爬虫模块导入失败: {str(e)}（请检查 crawler/ 目录）",
                "added_count": 0
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"爬虫执行异常: {type(e).__name__}: {str(e)}",
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
