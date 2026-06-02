"""
智联招聘爬虫模块。

使用 Playwright 同步模式访问搜索页，拦截 ``fe-api.zhaopin.com`` 职位列表接口，
结合 stealth 反检测与随机延时，将结果写入本地数据库。

运行示例::

    python crawler/zhilian_crawler.py --keyword Python --city 北京 --max-pages 5
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

# 项目根目录加入模块路径
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    sync_playwright,
)

from analysis.data_cleaner import DataCleaner
from config.settings import BASE_DIR
from storage.database import DatabaseManager, db_manager

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 数据来源标识
SOURCE_ZHILIAN: str = "zhilian"

# 每页职位数量（与智联 API 默认一致）
_PAGE_SIZE: int = 20

# 最大允许页数
_MAX_PAGES_LIMIT: int = 50

# 搜索页基础 URL
_SEARCH_PAGE_URL: str = "https://sou.zhaopin.com/"

# 职位列表 API 特征路径
_API_SOUPATH: str = "/c/i/sou"

# 城市名称 → 智联 cityId（常用城市）
CITY_ID_MAP: dict[str, int] = {
    "北京": 530,
    "上海": 538,
    "广州": 763,
    "深圳": 765,
    "杭州": 653,
    "成都": 801,
    "武汉": 736,
    "西安": 854,
    "南京": 635,
    "苏州": 639,
    "天津": 531,
    "重庆": 551,
    "长沙": 749,
    "郑州": 719,
    "青岛": 703,
    "厦门": 682,
    "合肥": 664,
    "大连": 600,
    "宁波": 654,
    "无锡": 636,
}

# 随机 User-Agent 池
_USER_AGENTS: list[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
]

# 内置 stealth 脚本（playwright-stealth 不可用时的兜底）
_STEALTH_INIT_SCRIPT: str = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters);
"""

# 字体加密常见私有区 Unicode（简单剔除）
_FONT_ENCRYPTED_PATTERN = re.compile(r"[\ue000-\uf8ff]")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def setup_logging(level: int = logging.INFO) -> None:
    """配置根日志格式。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def random_delay(min_sec: float = 1.5, max_sec: float = 4.0) -> None:
    """随机休眠，降低请求频率。"""
    time.sleep(random.uniform(min_sec, max_sec))


def decode_font_text(text: str | None) -> str:
    """
    简单处理字体加密文本。

    剔除 Unicode 私有区字符，并压缩空白。
    """
    if not text:
        return ""
    cleaned = _FONT_ENCRYPTED_PATTERN.sub("", str(text))
    return re.sub(r"\s+", " ", cleaned).strip()


def apply_stealth(page: Page) -> None:
    """
    为页面应用 stealth 反自动化检测。

    优先使用 ``playwright-stealth`` 插件，失败时回退到内置脚本。
    """
    try:
        from playwright_stealth import stealth_sync

        stealth_sync(page)
        logger.debug("已应用 playwright-stealth 插件")
    except ImportError:
        logger.warning("未安装 playwright-stealth，使用内置 stealth 脚本")
        page.add_init_script(_STEALTH_INIT_SCRIPT)
    except Exception as exc:
        logger.warning("playwright-stealth 应用失败: %s，使用内置脚本", exc)
        page.add_init_script(_STEALTH_INIT_SCRIPT)


def resolve_city_id(city: str) -> int:
    """
    解析城市名称为智联 ``cityId``。

    Args:
        city: 城市中文名，如「北京」。

    Returns:
        智联城市 ID。
    """
    name = city.strip().replace("市", "")
    if name in CITY_ID_MAP:
        return CITY_ID_MAP[name]
    for key, cid in CITY_ID_MAP.items():
        if key in name or name in key:
            return cid
    logger.warning("未找到城市 %s 的 cityId，默认使用北京(530)", city)
    return 530


# ---------------------------------------------------------------------------
# 智联爬虫
# ---------------------------------------------------------------------------


class ZhilianCrawler:
    """
    智联招聘职位爬虫。

    通过 Playwright 打开搜索页并拦截列表 API，解析后调用 ``db_manager.add_job`` 入库。
    """

    def __init__(
        self,
        keyword: str,
        city: str = "北京",
        max_pages: int = 10,
        *,
        db: DatabaseManager | None = None,
        headless: bool = True,
        fetch_detail: bool = False,
    ) -> None:
        """
        Args:
            keyword: 搜索关键词，如 ``Python``。
            city: 目标城市中文名。
            max_pages: 最大爬取页数（上限 50）。
            db: 数据库管理器，默认使用全局 ``db_manager``。
            headless: 是否无头模式运行浏览器。
            fetch_detail: 是否额外请求详情页补充描述（较慢）。
        """
        self.keyword = keyword.strip()
        self.city = city.strip()
        self.max_pages = max(1, min(max_pages, _MAX_PAGES_LIMIT))
        self._db = db or db_manager
        self.headless = headless
        self.fetch_detail = fetch_detail
        self.city_id = resolve_city_id(self.city)
        self._cleaner = DataCleaner()

        self._stats: dict[str, int] = {
            "pages_crawled": 0,
            "jobs_found": 0,
            "added": 0,
            "skipped": 0,
            "failed": 0,
        }

    def _build_search_url(self, page: int) -> str:
        """构造智联搜索页 URL。"""
        params = (
            f"kw={quote(self.keyword)}"
            f"&jl={self.city_id}"
            f"&p={page}"
            f"&sf=0&st=0"
        )
        return f"{_SEARCH_PAGE_URL}?{params}"

    def _build_api_url(self, start: int) -> str:
        """构造职位列表 API URL（用于主动请求兜底）。"""
        return (
            "https://fe-api.zhaopin.com/c/i/sou"
            f"?start={start}"
            f"&pageSize={_PAGE_SIZE}"
            f"&cityId={self.city_id}"
            f"&workExperience=-1"
            f"&education=-1"
            f"&companyType=-1"
            f"&employmentType=-1"
            f"&jobWelfareTag=-1"
            f"&kw={quote(self.keyword)}"
            f"&kt=3"
        )

    @staticmethod
    def _extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """从 API 响应 JSON 中提取职位列表。"""
        data = payload.get("data") or payload
        if isinstance(data, dict):
            for key in ("results", "list", "positionList", "dataList"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _parse_salary(self, salary_text: str | None) -> tuple[float | None, float | None]:
        """将薪资文本转为 (salary_min, salary_max)，单位 K/月。"""
        text = decode_font_text(salary_text)
        if not text:
            return None, None
        return self._cleaner._normalize_salary(text)

    def _parse_skills(self, item: dict[str, Any]) -> list[str] | None:
        """从 API 条目中提取技能标签列表。"""
        skills: list[str] = []

        for key in ("skillLabel", "jobSkill", "welfareTagList", "jobLabels"):
            value = item.get(key)
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, str):
                        skills.append(entry)
                    elif isinstance(entry, dict):
                        name = entry.get("name") or entry.get("value")
                        if name:
                            skills.append(str(name))

        # positionLabel 中可能包含 jobLight JSON 字符串
        label_raw = item.get("positionLabel")
        if isinstance(label_raw, str) and "jobLight" in label_raw:
            match = re.search(r'"jobLight"\s*:\s*\[(.*?)\]', label_raw, re.S)
            if match:
                inner = match.group(1)
                parts = re.findall(r'"([^"]+)"', inner)
                skills.extend(parts)

        keyword = item.get("keyword")
        if isinstance(keyword, str) and keyword.strip():
            skills.extend(re.split(r"[,，\s]+", keyword))

        skills = [decode_font_text(s) for s in skills if s]
        skills = list(dict.fromkeys(s for s in skills if s))
        return skills or None

    def _parse_job_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """
        将单条 API 职位数据转换为 ``add_job`` 所需字典。

        Returns:
            职位字典；必填字段缺失时返回 ``None``。
        """
        title = decode_font_text(
            item.get("jobName") or item.get("name") or item.get("positionName")
        )
        company_info = item.get("company") or {}
        company = decode_font_text(
            item.get("companyName")
            or (company_info.get("name") if isinstance(company_info, dict) else None)
            or item.get("companyNameWithoutFormat")
        )

        city_info = item.get("city") or {}
        city_display = (
            city_info.get("display")
            if isinstance(city_info, dict)
            else item.get("cityName")
        )
        city_name = decode_font_text(city_display) or self.city

        district = None
        if isinstance(city_info, dict):
            district = decode_font_text(
                city_info.get("district") or city_info.get("areaDistrict")
            )

        salary_raw = decode_font_text(item.get("salary"))
        salary_min, salary_max = self._parse_salary(salary_raw)

        exp_info = item.get("workingExp") or item.get("workExperience") or {}
        experience = decode_font_text(
            exp_info.get("name")
            if isinstance(exp_info, dict)
            else item.get("experience")
        )

        edu_info = item.get("eduLevel") or item.get("education") or {}
        education = decode_font_text(
            edu_info.get("name")
            if isinstance(edu_info, dict)
            else item.get("education")
        )

        industry_info = item.get("industryType") or company_info.get("industry") or {}
        industry = decode_font_text(
            industry_info.get("name")
            if isinstance(industry_info, dict)
            else item.get("industry")
        )

        company_size_info = company_info.get("size") if isinstance(company_info, dict) else {}
        company_size = (
            company_size_info.get("name")
            if isinstance(company_size_info, dict)
            else None
        )

        company_type_info = company_info.get("type") if isinstance(company_info, dict) else {}
        company_type = (
            company_type_info.get("name")
            if isinstance(company_type_info, dict)
            else None
        )

        description = decode_font_text(
            item.get("jobSummary")
            or item.get("jobDescribe")
            or item.get("description")
        )

        url = item.get("positionURL") or item.get("positionUrl") or item.get("url")
        if not url and item.get("number"):
            url = f"https://www.zhaopin.com/jobdetail/{item.get('number')}.htm"

        if not title or not company:
            logger.debug("跳过无效条目（缺少标题或公司）: %s", item)
            return None

        return {
            "title": title[:200],
            "company": company[:200],
            "city": (city_name or self.city)[:50],
            "district": district[:50] if district else None,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "experience": experience[:50] if experience else None,
            "education": education[:50] if education else None,
            "skills": self._parse_skills(item),
            "company_size": decode_font_text(company_size)[:50] if company_size else None,
            "company_type": decode_font_text(company_type)[:50] if company_type else None,
            "industry": decode_font_text(industry)[:100] if industry else None,
            "description": description,
            "url": str(url)[:500] if url else None,
            "source": SOURCE_ZHILIAN,
            "is_simulated": False,
        }

    def _save_job(self, job_data: dict[str, Any]) -> None:
        """写入数据库并更新统计。"""
        try:
            job_id = self._db.add_job(job_data)
            if job_id is None:
                self._stats["skipped"] += 1
                logger.debug("跳过重复 URL: %s", job_data.get("url"))
            else:
                self._stats["added"] += 1
                logger.info(
                    "入库成功 [%s] %s - %s",
                    job_id,
                    job_data.get("title"),
                    job_data.get("company"),
                )
        except Exception as exc:
            self._stats["failed"] += 1
            logger.error("入库失败 %s: %s", job_data.get("title"), exc)

    def _fetch_api_via_browser(self, page: Page, start: int) -> list[dict[str, Any]]:
        """通过浏览器上下文主动请求 API（兜底方案）。"""
        api_url = self._build_api_url(start)
        try:
            response = page.request.get(
                api_url,
                headers={
                    "User-Agent": random.choice(_USER_AGENTS),
                    "Referer": _SEARCH_PAGE_URL,
                    "Accept": "application/json, text/plain, */*",
                },
            )
            if not response.ok:
                logger.warning("API 请求失败 start=%s status=%s", start, response.status)
                return []
            payload = response.json()
            return self._extract_results(payload)
        except Exception as exc:
            logger.error("API 请求异常 start=%s: %s", start, exc)
            return []

    def _fetch_detail_description(self, page: Page, item: dict[str, Any]) -> str | None:
        """
        请求职位详情补充描述（可选，较慢）。

        Args:
            page: Playwright 页面对象。
            item: 列表 API 返回的单条职位。

        Returns:
            职位描述文本或 ``None``。
        """
        number = item.get("number") or item.get("jobNumber")
        if not number:
            return None

        detail_url = f"https://fe-api.zhaopin.com/c/i/job/detail?number={number}"
        try:
            response = page.request.get(
                detail_url,
                headers={"Referer": _SEARCH_PAGE_URL},
            )
            if not response.ok:
                return None
            payload = response.json()
            detail = payload.get("data") or {}
            return decode_font_text(
                detail.get("jobDetail")
                or detail.get("description")
                or detail.get("jobDescribe")
            )
        except Exception as exc:
            logger.debug("详情获取失败 number=%s: %s", number, exc)
            return None

    def _process_items(self, page: Page, items: list[dict[str, Any]]) -> None:
        """解析并入库一批职位。"""
        self._stats["jobs_found"] += len(items)
        for item in items:
            job_data = self._parse_job_item(item)
            if not job_data:
                self._stats["failed"] += 1
                continue

            if self.fetch_detail and not job_data.get("description"):
                random_delay(0.8, 1.8)
                desc = self._fetch_detail_description(page, item)
                if desc:
                    job_data["description"] = desc

            self._save_job(job_data)

    def _crawl_page(self, page: Page, page_num: int) -> bool:
        """
        爬取单页搜索结果。

        Returns:
            是否成功获取到数据；``False`` 表示可能已到末页。
        """
        captured: list[dict[str, Any]] = []

        def on_response(response: Response) -> None:
            if _API_SOUPATH not in response.url:
                return
            try:
                if response.status != 200:
                    return
                payload = response.json()
                results = self._extract_results(payload)
                if results:
                    captured.extend(results)
                    logger.debug(
                        "拦截 API 响应 page=%s count=%s", page_num, len(results)
                    )
            except Exception:
                pass

        page.on("response", on_response)
        search_url = self._build_search_url(page_num)
        logger.info("正在爬取第 %s 页: %s", page_num, search_url)

        try:
            page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            page.wait_for_timeout(random.randint(1500, 3000))
        except Exception as exc:
            logger.error("页面加载失败 page=%s: %s", page_num, exc)
        finally:
            page.remove_listener("response", on_response)

        # 若未拦截到 API，使用主动请求兜底
        if not captured:
            start = (page_num - 1) * _PAGE_SIZE
            logger.info("未拦截到 API，尝试主动请求 start=%s", start)
            captured = self._fetch_api_via_browser(page, start)

        # DOM 兜底：简单解析页面卡片（应对 API 完全不可用）
        if not captured:
            captured = self._parse_dom_cards(page)

        if not captured:
            logger.warning("第 %s 页未获取到职位数据", page_num)
            return False

        self._process_items(page, captured)
        self._stats["pages_crawled"] += 1
        return True

    def _parse_dom_cards(self, page: Page) -> list[dict[str, Any]]:
        """
        DOM 解析兜底（简化版）。

        当 API 拦截失败时，从页面职位卡片提取基础字段。
        """
        items: list[dict[str, Any]] = []
        selectors = [
            ".joblist-box__item",
            ".positionlist__item",
            ".jobList .job_item",
            "[class*='joblist'] [class*='item']",
        ]

        cards = []
        for selector in selectors:
            cards = page.query_selector_all(selector)
            if cards:
                break

        for card in cards[:30]:
            try:
                title_el = card.query_selector("a[href*='jobdetail'], .jobinfo__name, .job-name")
                company_el = card.query_selector(
                    ".companyinfo__name, .company-name, .company__name"
                )
                salary_el = card.query_selector(
                    ".jobinfo__salary, .salary, [class*='salary']"
                )
                if not title_el:
                    continue

                title = decode_font_text(title_el.inner_text())
                company = decode_font_text(
                    company_el.inner_text() if company_el else "未知公司"
                )
                salary = decode_font_text(
                    salary_el.inner_text() if salary_el else ""
                )
                href = title_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = f"https://www.zhaopin.com{href}"

                items.append(
                    {
                        "jobName": title,
                        "companyName": company,
                        "salary": salary,
                        "city": {"display": self.city},
                        "positionURL": href,
                    }
                )
            except Exception:
                continue

        if items:
            logger.info("DOM 兜底解析到 %s 条职位", len(items))
        return items

    def _create_context(self, browser: Browser) -> BrowserContext:
        """创建带随机 UA 与请求头的浏览器上下文。"""
        ua = random.choice(_USER_AGENTS)
        context = browser.new_context(
            user_agent=ua,
            viewport={
                "width": random.randint(1280, 1920),
                "height": random.randint(720, 1080),
            },
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        return context

    def run(self) -> dict[str, int]:
        """
        执行爬取任务。

        Returns:
            统计信息字典。
        """
        logger.info(
            "开始爬取 | 关键词=%s | 城市=%s(cityId=%s) | 最大页数=%s",
            self.keyword,
            self.city,
            self.city_id,
            self.max_pages,
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = self._create_context(browser)
            page = context.new_page()
            apply_stealth(page)

            try:
                # 先访问首页建立 Cookie，降低后续 API 拦截失败概率
                page.goto(_SEARCH_PAGE_URL, wait_until="domcontentloaded", timeout=60_000)
                random_delay(2.0, 4.0)

                for page_num in range(1, self.max_pages + 1):
                    has_data = self._crawl_page(page, page_num)
                    if not has_data and page_num > 1:
                        logger.info("第 %s 页无数据，停止翻页", page_num)
                        break
                    if page_num < self.max_pages:
                        random_delay(2.0, 5.0)
            finally:
                context.close()
                browser.close()

        logger.info(
            "爬取结束 | 页数=%s | 发现=%s | 入库=%s | 跳过=%s | 失败=%s",
            self._stats["pages_crawled"],
            self._stats["jobs_found"],
            self._stats["added"],
            self._stats["skipped"],
            self._stats["failed"],
        )
        return dict(self._stats)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="智联招聘职位爬虫（Playwright + stealth）",
    )
    parser.add_argument(
        "-k",
        "--keyword",
        default="Python",
        help="搜索关键词（默认: Python）",
    )
    parser.add_argument(
        "-c",
        "--city",
        default="北京",
        help="目标城市（默认: 北京）",
    )
    parser.add_argument(
        "-p",
        "--max-pages",
        type=int,
        default=10,
        help="最大爬取页数，上限 50（默认: 10）",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="显示浏览器窗口（调试用）",
    )
    parser.add_argument(
        "--fetch-detail",
        action="store_true",
        help="额外请求详情接口补充职位描述（较慢）",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出 DEBUG 日志",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    命令行入口。

    Returns:
        进程退出码，0 表示成功。
    """
    args = parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    crawler = ZhilianCrawler(
        keyword=args.keyword,
        city=args.city,
        max_pages=min(args.max_pages, _MAX_PAGES_LIMIT),
        headless=not args.no_headless,
        fetch_detail=args.fetch_detail,
    )

    try:
        stats = crawler.run()
    except KeyboardInterrupt:
        logger.warning("用户中断爬取")
        return 130
    except Exception as exc:
        logger.exception("爬取异常终止: %s", exc)
        return 1

    if stats["added"] == 0 and stats["pages_crawled"] == 0:
        logger.error(
            "未成功爬取任何数据。请检查网络、Playwright 安装或尝试 --no-headless 调试。"
        )
        return 2

    logger.info("数据目录: %s", BASE_DIR / "data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
