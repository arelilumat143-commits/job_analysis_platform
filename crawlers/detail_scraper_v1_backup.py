# ============================================================
# detail_scraper.py — 职位详情页异步爬虫
# 功能：抓取职位详情页，补充 experience/education/skills/
#       industry/company_size/company_type/description 等缺失字段
# 用法：
#   python detail_scraper.py                    # 爬取全部 NULL 字段的职位
#   python detail_scraper.py --city 北京         # 按城市筛选
#   python detail_scraper.py --limit 100         # 限制数量
#   python detail_scraper.py --concurrency 10    # 并发数
# ============================================================
import asyncio
import aiohttp
import argparse
import json
import re
import sys
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from storage.database import db_manager


class DetailScraper:
    """职位详情页异步爬虫"""

    # 进度文件路径
    PROGRESS_FILE = Path(__file__).resolve().parent / 'detail_scraper_progress.json'

    def __init__(self, concurrency=5, delay_range=(1.0, 3.0), timeout=15):
        """
        Args:
            concurrency: 并发请求数
            delay_range: 请求间隔范围(秒)，随机在此区间内
            timeout: 单个请求超时时间(秒)
        """
        self.concurrency = concurrency
        self.delay_range = delay_range
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(concurrency)
        self.db = db_manager

        # 统计
        self.stats = {
            'total': 0, 'success': 0, 'failed': 0,
            'skipped': 0, 'updated': 0,
            'start_time': None, 'last_id': 0,
        }
        # 进度回调（可选，用于 API 实时通知）
        self.progress_callback = None

    # ========== 进度持久化 ==========

    def load_progress(self) -> dict:
        if self.PROGRESS_FILE.exists():
            try:
                return json.loads(self.PROGRESS_FILE.read_text())
            except Exception:
                pass
        return {'last_id': 0, 'updated': 0, 'failed_ids': []}

    def save_progress(self, last_id):
        data = {
            'last_id': last_id,
            'updated': self.stats['updated'],
            'failed_ids': [],
            'updated_at': datetime.now().isoformat(),
        }
        self.PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # ========== HTTP 请求 ==========

    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """获取页面HTML，带重试"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        for attempt in range(3):
            try:
                async with self.semaphore:
                    # 随机延迟防止反爬
                    delay = self.delay_range[0] + (self.delay_range[1] - self.delay_range[0]) * (
                        (time.time() * 1000 % 1000) / 1000
                    )
                    await asyncio.sleep(delay)
                    async with session.get(url, headers=headers, timeout=self.timeout,
                                           allow_redirects=True, ssl=False) as resp:
                        if resp.status == 200:
                            return await resp.text()
                        elif resp.status in (404, 410):
                            return None  # 页面不存在
                        # 其他状态码重试
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == 2:
                    print(f'  [FAIL] {url[:80]}... — {e}')
                await asyncio.sleep(2 ** attempt)
        return None

    # ========== HTML 解析 ==========

    def parse_detail(self, html: str, url: str) -> Dict[str, Optional[str]]:
        """从详情页HTML中提取缺失字段"""
        soup = BeautifulSoup(html, 'lxml')
        result = {}

        # ---- 经验/学历 ----
        # 智联页面常见模式：在职位描述区块的 <li> 或 <span> 中
        # 尝试从职位要求列表中匹配
        result['experience'] = self._extract_field(soup, ['经验', '工作经验'])
        result['education'] = self._extract_field(soup, ['学历', '学历要求'])
        result['skills'] = self._extract_skills(soup)
        result['industry'] = self._extract_industry(soup)
        result['company_size'] = self._extract_field(soup, ['公司规模', '规模', '人数'])
        result['company_type'] = self._extract_field(soup, ['公司性质', '公司类型', '企业性质', '性质'])
        result['description'] = self._extract_description(soup)

        return result

    def _extract_field(self, soup: BeautifulSoup, labels: List[str]) -> Optional[str]:
        """根据标签名提取字段值，如 '经验：3-5年' → '3-5年'"""
        text = soup.get_text()

        for label in labels:
            # 模式: "经验：3-5年" 或 "经验 3-5年" 或 "3-5年经验"
            patterns = [
                rf'{label}[：:\s]*([^\s\n,，。]+)',
                rf'([^\s\n,，。]+)[\s]*{label}',
            ]
            for pat in patterns:
                m = re.search(pat, text)
                if m and len(m.group(1)) > 0 and len(m.group(1)) < 30:
                    val = m.group(1).strip('：: 　')
                    if val and not any(kw in val for kw in ['不限', '若干', '面议']):
                        return val
        return None

    def _extract_skills(self, soup: BeautifulSoup) -> Optional[str]:
        """提取技能标签"""
        # 尝试找标签容器
        tag_selectors = [
            '.job-tags .item', '.skill-tag', '.tag-list li',
            '.job-demand .tag', '.skills span', '[class*="skill"] span',
            '[class*="tag"] a', '.job-qualify .tag',
        ]
        for selector in tag_selectors:
            tags = soup.select(selector)
            if tags and len(tags) >= 2:
                skills = [t.get_text(strip=True) for t in tags[:20]]
                return ','.join(skills)

        # 尝试从文本中提取
        text = soup.get_text()
        m = re.search(r'(?:技能|技术栈|技术要求)[：:\s]*([^\n]{10,200})', text)
        if m:
            skills_text = m.group(1)
            # 按常见分隔符切分
            skills = re.split(r'[,，、/|；;]', skills_text)
            skills = [s.strip() for s in skills if 1 < len(s.strip()) < 20]
            if len(skills) >= 2:
                return ','.join(skills[:20])

        return None

    def _extract_industry(self, soup: BeautifulSoup) -> Optional[str]:
        """提取行业信息"""
        # 通常在面包屑或公司信息中
        breadcrumb = soup.select_one('.breadcrumb, .crumbs, [class*="breadcrumb"]')
        if breadcrumb:
            text = breadcrumb.get_text(strip=True)
            # 常见的行业关键词
            industries = ['互联网', 'IT', '金融', '教育', '医疗', '制造', '房地产',
                          '人工智能', '电商', '游戏', '通信', '能源', '物流', '汽车',
                          '快消', '咨询', '法律', '传媒', '旅游', '餐饮']
            for ind in industries:
                if ind in text:
                    return ind

        # 尝试匹配 "所属行业：XXX"
        m = re.search(r'(?:所属)?行业[：:\s]*(\S{2,20})', soup.get_text())
        if m:
            return m.group(1)

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """提取职位描述正文"""
        desc_selectors = [
            '.job-detail', '.describtion', '.job-description',
            '.job-desc', '.job-content', '[class*="detail"]',
            '.job-main', '.responsibility', '.job-duty',
        ]
        for selector in desc_selectors:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator='\n', strip=True)
                if len(text) > 30:
                    return text[:5000]  # 限制长度

        # 降级：尝试获取包含大量文字的主体区域
        main = soup.select_one('article, .main, .content, .job-box')
        if main:
            text = main.get_text(separator='\n', strip=True)
            if len(text) > 50:
                return text[:3000]

        return None

    # ========== 数据库操作 ==========

    def get_jobs_to_scrape(self, city: Optional[str] = None, limit: Optional[int] = None,
                           resume_from: int = 0) -> List[Dict]:
        """获取需要爬取详情的职位列表"""
        with self.db.get_session() as session:
            from storage.models import Job
            q = session.query(Job).filter(
                Job.url.isnot(None),
                Job.url != '',
                Job.url.like('%zhaopin.com%'),  # 只抓智联的详情页
            )
            # 只抓缺失字段的
            q = q.filter(
                (Job.experience.is_(None)) |
                (Job.education.is_(None)) |
                (Job.skills.is_(None))
            )
            if city:
                q = q.filter(Job.city == city)
            if resume_from:
                q = q.filter(Job.id > resume_from)
            q = q.order_by(Job.id)
            if limit:
                q = q.limit(limit)

            jobs = q.all()
            return [j.to_dict() for j in jobs]

    def update_job(self, job_id: int, data: Dict[str, Optional[str]]) -> bool:
        """更新单条职位的详情字段"""
        # 只更新非空字段
        updates = {k: v for k, v in data.items() if v is not None}
        if not updates:
            return False
        try:
            with self.db.get_session() as session:
                from storage.models import Job
                job = session.query(Job).filter(Job.id == job_id).first()
                if job:
                    for key, val in updates.items():
                        if hasattr(job, key) and getattr(job, key) is None:
                            setattr(job, key, val)
                    session.commit()
                    return True
        except Exception as e:
            print(f'  [DB ERROR] id={job_id}: {e}')
        return False

    # ========== 主流程 ==========

    async def run(self, city: Optional[str] = None, limit: Optional[int] = None,
                  resume: bool = True):
        """运行详情爬虫"""
        print(f'========== 详情页爬虫启动 ==========')
        print(f'并发数: {self.concurrency} | 延迟: {self.delay_range[0]}-{self.delay_range[1]}秒')

        # 加载进度
        resume_from = 0
        if resume:
            progress = self.load_progress()
            resume_from = progress.get('last_id', 0)
            if resume_from:
                print(f'从 ID={resume_from} 恢复，已完成 {progress.get("updated", 0)} 条')

        # 获取待爬列表
        jobs = self.get_jobs_to_scrape(city=city, limit=limit, resume_from=resume_from)
        self.stats['total'] = len(jobs)
        self.stats['start_time'] = time.time()

        if not jobs:
            print('没有需要爬取的职位。')
            return self.stats

        print(f'待爬取: {len(jobs)} 条')
        if limit:
            est_time = limit * (self.delay_range[1]) / self.concurrency / 60
            print(f'预计耗时: {est_time:.0f} 分钟')

        # 异步批量抓取
        connector = aiohttp.TCPConnector(limit=self.concurrency, force_close=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            batch_size = 50  # 每50条打印一次进度
            last_report = 0

            for i, job in enumerate(jobs):
                task = asyncio.create_task(self._scrape_one(session, job))
                tasks.append(task)

                # 分批等待完成
                if len(tasks) >= batch_size or i == len(jobs) - 1:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks = []

                    # 进度报告
                    if self.stats['success'] - last_report >= batch_size or i == len(jobs) - 1:
                        elapsed = time.time() - self.stats['start_time']
                        rate = (i + 1) / elapsed * 60 if elapsed > 0 else 0
                        print(f'  进度: {i + 1}/{len(jobs)} '
                              f'| 成功:{self.stats["success"]} 更新:{self.stats["updated"]} '
                              f'失败:{self.stats["failed"]} | {rate:.1f}条/分钟')

                        if self.progress_callback:
                            self.progress_callback(self.stats.copy())

                        last_report = self.stats['success']
                        self.save_progress(jobs[i]['id'])

        # 总结
        elapsed = time.time() - self.stats['start_time']
        print(f'\n========== 完成 ==========')
        print(f'总数: {self.stats["total"]} | 成功: {self.stats["success"]} | '
              f'更新: {self.stats["updated"]} | 失败: {self.stats["failed"]} | '
              f'跳过: {self.stats["skipped"]}')
        print(f'耗时: {elapsed / 60:.1f} 分钟')
        return self.stats

    async def _scrape_one(self, session: aiohttp.ClientSession, job: Dict):
        """抓取单条职位详情"""
        job_id = job['id']
        url = job.get('url', '')

        if not url or 'zhaopin.com' not in url:
            self.stats['skipped'] += 1
            return

        html = await self.fetch_page(session, url)
        if not html:
            self.stats['failed'] += 1
            return

        self.stats['success'] += 1

        try:
            data = self.parse_detail(html, url)
            if any(v is not None for v in data.values()):
                updated = self.update_job(job_id, data)
                if updated:
                    self.stats['updated'] += 1
        except Exception as e:
            print(f'  [PARSE ERROR] id={job_id}: {e}')


# ========== 命令行入口 ==========

def main():
    parser = argparse.ArgumentParser(description='职位详情页异步爬虫')
    parser.add_argument('--city', type=str, default=None, help='按城市筛选')
    parser.add_argument('--limit', type=int, default=100, help='限制数量(默认100)')
    parser.add_argument('--concurrency', type=int, default=5, help='并发数(默认5)')
    parser.add_argument('--delay-min', type=float, default=1.0, help='最小延迟秒数')
    parser.add_argument('--delay-max', type=float, default=3.0, help='最大延迟秒数')
    parser.add_argument('--no-resume', action='store_true', help='不恢复进度')
    args = parser.parse_args()

    scraper = DetailScraper(
        concurrency=args.concurrency,
        delay_range=(args.delay_min, args.delay_max),
    )
    asyncio.run(scraper.run(
        city=args.city,
        limit=args.limit,
        resume=not args.no_resume,
    ))


if __name__ == '__main__':
    main()
