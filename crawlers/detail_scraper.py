# ============================================================
# detail_scraper.py — 职位详情页异步爬虫 (v4 TLS 指纹伪装版)
# 功能：抓取职位详情页，补充 experience/education/skills/
#       industry/company_size/company_type/description 等缺失字段
#
# v4 改进：
#   - curl_cffi 替代 requests，模拟 Chrome TLS 指纹绕过 EdgeOne
#   - 共享 Session 持久化 Cookie
#   - 从智联 script 标签 JSON 精确提取结构化字段
# 用法：
#   python detail_scraper.py                    # 爬取全部 NULL 字段
#   python detail_scraper.py --city 北京         # 按城市筛选
#   python detail_scraper.py --limit 100         # 限制数量
# ============================================================
import asyncio
import argparse
import json
import re
import sys
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# curl_cffi 模拟 Chrome TLS 指纹，绕过腾讯 EdgeOne 防护
from curl_cffi import requests as cffi_requests

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from storage.database import db_manager


class DetailScraper:
    """职位详情页异步爬虫（TLS 指纹伪装版）"""

    PROGRESS_FILE = Path(__file__).resolve().parent / 'detail_scraper_progress.json'

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(self, concurrency=5, delay_range=(1.0, 3.0), timeout=15):
        self.concurrency = concurrency
        self.delay_range = delay_range
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(concurrency)
        self.db = db_manager

        # 共享的 curl_cffi session（在线程池中复用）
        self._session = cffi_requests.Session()
        self._session_requests = 0
        self._session_max_requests = 200  # 每200次请求重建session

        self.stats = {
            'total': 0, 'success': 0, 'failed': 0,
            'skipped': 0, 'updated': 0,
            'start_time': None, 'last_id': 0,
        }
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

    def _get_session(self):
        """获取或刷新 session（每 N 次请求重建，保持 Cookie 新鲜）"""
        self._session_requests += 1
        if self._session_requests > self._session_max_requests:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = cffi_requests.Session()
            self._session_requests = 0
        return self._session

    def _fetch_sync(self, url: str) -> Optional[str]:
        """同步获取页面HTML（curl_cffi，模拟 Chrome 120 TLS 指纹）"""
        session = self._get_session()
        headers = {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Google Chrome";v="120", "Chromium";v="120", "Not?A_Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Upgrade-Insecure-Requests': '1',
        }

        for attempt in range(3):
            try:
                # curl_cffi 模拟 Chrome 120 TLS 指纹
                resp = session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False,
                    impersonate="chrome120",  # 关键：模拟 Chrome 120 的 TLS 指纹
                )
                if resp.status_code == 200:
                    html = resp.text
                    # 检测反爬页面（Security Verification + EdgeOne JS Challenge）
                    is_blocked = (
                        'Security Verification' in html or
                        '__TENCENT_CHAOS_VM' in html or
                        'solveChallenge' in html or
                        len(html) < 5000
                    )
                    if is_blocked:
                        if attempt < 2:
                            time.sleep(1.5 ** attempt)
                            # 反爬后重建 session
                            try:
                                self._session.close()
                            except Exception:
                                pass
                            self._session = cffi_requests.Session()
                            self._session_requests = 0
                            continue
                        return None
                    return html
                elif resp.status_code in (404, 410):
                    return None
            except Exception:
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return None

    async def fetch_page(self, url: str) -> Optional[str]:
        """异步包装：在线程池中执行同步请求"""
        async with self.semaphore:
            delay = self.delay_range[0] + random.random() * (self.delay_range[1] - self.delay_range[0])
            await asyncio.sleep(delay)
            return await asyncio.to_thread(self._fetch_sync, url)

    # ========== HTML 解析 ==========

    def parse_detail(self, html: str, url: str) -> Dict[str, Optional[str]]:
        """从智联详情页HTML中提取缺失字段"""
        soup = BeautifulSoup(html, 'lxml')
        result = {}

        json_data = self._extract_page_json(html)

        result['experience'] = (
            json_data.get('workingExp') or
            json_data.get('positionWorkingExp')
        )
        result['education'] = json_data.get('education')
        result['company_size'] = json_data.get('companySize')
        result['industry'] = (
            json_data.get('industryLevel') or
            json_data.get('industryNameLevel')
        )
        result['company_type'] = json_data.get('companyType')
        result['skills'] = self._extract_skills(soup, json_data)
        result['description'] = (
            self._extract_description(soup) or
            json_data.get('positionDetail') or
            json_data.get('description') or
            json_data.get('companyDescription')
        )

        return result

    def _extract_page_json(self, html: str) -> Dict[str, Optional[str]]:
        """从智联页面 script 提取结构化 JSON 数据"""
        result = {}

        patterns = {
            'workingExp': r'"workingExp"\s*:\s*"([^"]+)"',
            'education': r'"education"\s*:\s*"([^"]+)"',
            'companySize': r'"companySize"\s*:\s*"([^"]+)"',
            'industryLevel': r'"industry(?:Name)?Level"\s*:\s*"([^"]+)"',
            'positionWorkingExp': r'"positionWorkingExp"\s*:\s*"([^"]+)"',
            'companyType': r'"companyType"\s*:\s*"([^"]+)"',
            'companyDescription': r'"companyDescription"\s*:\s*"([^"]{20,2000})"',
            'positionDetail': r'"positionDetail"\s*:\s*"([^"]{50,5000})"',
            'description': r'"description"\s*:\s*"([^"]{20,500})"',
        }

        for key, pattern in patterns.items():
            m = re.search(pattern, html)
            if m:
                result[key] = m.group(1)

        return result

    def _extract_skills(self, soup: BeautifulSoup, json_data: Dict) -> Optional[str]:
        """从 HTML 提取技能标签"""
        tag_selectors = [
            '.job-welfare__item', '.job-tags .item', '.job-qualify .tag',
            '.job-demand .tag', '.skill-tag', '.tag-list li',
            '[class*="skill"] span', '[class*="tag"] a',
        ]
        welfare_words = {'五险一金', '周末双休', '带薪年假', '弹性工作', '年终奖',
                         '交通补贴', '餐补', '通讯补贴', '定期体检', '员工旅游',
                         '节日福利', '公积金', '补充医疗', '包吃', '包住', '全勤奖',
                         '绩效奖金', '股票期权', '免费班车', '零食', '下午茶'}

        for selector in tag_selectors:
            tags = soup.select(selector)
            if tags and len(tags) >= 2:
                skills = [t.get_text(strip=True) for t in tags[:20]]
                technical = [s for s in skills if s not in welfare_words and len(s) > 1]
                if len(technical) >= 2:
                    return ','.join(technical[:20])
                if len(skills) >= 2:
                    return ','.join(skills[:20])

        text = soup.get_text()
        m = re.search(r'(?:技能|技术栈|技术要求|任职要求)[：:\s]*([^\n]{10,300})', text)
        if m:
            skills_text = m.group(1)
            skills = re.split(r'[,，、/|；;]', skills_text)
            skills = [s.strip() for s in skills if 1 < len(s.strip()) < 20]
            if len(skills) >= 2:
                return ','.join(skills[:20])

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """从HTML提取职位描述正文"""
        desc_selectors = [
            '.describtion', '.job-detail', '.job-content', '.job-desc',
            '.responsibility', '.job-duty', '[class*="detail"]',
            '[class*="desc"]', '.job-main',
        ]
        for selector in desc_selectors:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator='\n', strip=True)
                if len(text) > 30:
                    return text[:5000]

        for selector in ['article', '.main', '.content', '.job-box']:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator='\n', strip=True)
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
                Job.url.like('%zhaopin.com%'),
            )
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
        """更新单条职位的详情字段（只更新还是NULL的字段）"""
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
        print(f'========== 详情页爬虫启动 (v4 TLS伪装) ==========')
        print(f'并发数: {self.concurrency} | 延迟: {self.delay_range[0]}-{self.delay_range[1]}秒')

        resume_from = 0
        if resume:
            progress = self.load_progress()
            resume_from = progress.get('last_id', 0)
            if resume_from:
                print(f'从 ID={resume_from} 恢复，已完成 {progress.get("updated", 0)} 条')

        jobs = self.get_jobs_to_scrape(city=city, limit=limit, resume_from=resume_from)
        self.stats['total'] = len(jobs)
        self.stats['start_time'] = time.time()

        if not jobs:
            print('没有需要爬取的职位。')
            return self.stats

        print(f'待爬取: {len(jobs)} 条')

        tasks = []
        batch_size = 50
        last_report = 0

        for i, job in enumerate(jobs):
            task = asyncio.create_task(self._scrape_one(job))
            tasks.append(task)

            if len(tasks) >= batch_size or i == len(jobs) - 1:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

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

        elapsed = time.time() - self.stats['start_time']
        print(f'\n========== 完成 ==========')
        print(f'总数: {self.stats["total"]} | 成功: {self.stats["success"]} | '
              f'更新: {self.stats["updated"]} | 失败: {self.stats["failed"]} | '
              f'跳过: {self.stats["skipped"]}')
        print(f'耗时: {elapsed / 60:.1f} 分钟')
        return self.stats

    async def _scrape_one(self, job: Dict):
        """抓取单条职位详情"""
        job_id = job['id']
        url = job.get('url', '')

        if not url or 'zhaopin.com' not in url:
            self.stats['skipped'] += 1
            return

        html = await self.fetch_page(url)
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
        except Exception:
            pass


# ========== 命令行入口 ==========

def main():
    parser = argparse.ArgumentParser(description='职位详情页异步爬虫')
    parser.add_argument('--city', type=str, default=None, help='按城市筛选')
    parser.add_argument('--limit', type=int, default=100, help='限制数量(默认100)')
    parser.add_argument('--concurrency', type=int, default=5, help='并发数(默认5)')
    parser.add_argument('--delay-min', type=float, default=1.5, help='最小延迟秒数')
    parser.add_argument('--delay-max', type=float, default=3.5, help='最大延迟秒数')
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
