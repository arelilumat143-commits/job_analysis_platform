"""
异步高性能智联招聘爬虫模块（生产级优化版）。

技术栈：asyncio + aiohttp + Playwright 混合模式。
核心特性：
  - 三级数据获取：aiohttp API → Playwright 浏览器 API → DOM 解析兜底
  - 详情页 Playwright 深度抓取（description + skills 完整补充）
  - 智能反爬：随机 UA 池（桌面+移动端）、指数退避重试、Cookie 自动刷新
  - 断点续爬：关键词+城市+页码粒度，中断后可从上次位置继续
  - 速度档位：--speed fast/normal/safe 自动调整并发与延时
  - 自动清洗入库：每条数据经 DataCleaner 标准化后写入 MySQL

运行示例::

    # 基础用法
    python crawler/async_zhilian_crawler.py -k Python -c 北京

    # 多关键词（逗号分隔）+ 多城市 + 安全模式
    python crawler/async_zhilian_crawler.py -k "Python,Java,前端" -c 北京 上海 --speed safe

    # 大规模爬取（禁用断点，抓详情）
    python crawler/async_zhilian_crawler.py -k Python -c 北京 -p 15 -n 8 --no-resume
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os as _os
import platform
import random
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

# 项目根目录加入模块路径
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector

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

SOURCE_ZHILIAN: str = "zhilian"
_PAGE_SIZE: int = 20
_MAX_PAGES_LIMIT: int = 50
_API_HOST: str = "https://fe-api.zhaopin.com"
_API_SEARCH_PATH: str = "/c/i/sou"
_API_DETAIL_PATH: str = "/c/i/job/detail"
_SEARCH_PAGE_URL: str = "https://sou.zhaopin.com/"
_DETAIL_PAGE_URL: str = "https://www.zhaopin.com/jobdetail/{number}.htm"
_CHECKPOINT_FILE: str = "crawl_checkpoint.json"
_DETAIL_CONCURRENCY: int = 4
_COOKIE_REFRESH_INTERVAL: int = 1200  # 20 分钟自动刷新 Cookie
_COOKIE_FORCE_REFRESH_ON_ERRORS: int = 2  # 连续 N 次 403 后强制刷新

# ---------------------------------------------------------------------------
# 速度档位预设（并发数, 最小延时, 最大延时, 详情并发）
# ---------------------------------------------------------------------------

SpeedPreset = dict[str, tuple[int, float, float, int]]

_SPEED_PRESETS: SpeedPreset = {
    "fast": (8, 0.5, 1.5, 6),    # 快速：并发 8，延时 0.5-1.5s
    "normal": (6, 1.0, 3.0, 4),  # 正常：并发 6，延时 1.0-3.0s（默认）
    "safe": (4, 2.0, 5.0, 2),    # 安全：并发 4，延时 2.0-5.0s
}

# ---------------------------------------------------------------------------
# 城市名称 → 智联 cityId 映射表
# ---------------------------------------------------------------------------

CITY_ID_MAP: dict[str, int] = {
    "北京": 530, "上海": 538, "广州": 763, "深圳": 765,
    "杭州": 653, "成都": 801, "武汉": 736, "西安": 854,
    "南京": 635, "苏州": 639, "天津": 531, "重庆": 551,
    "长沙": 749, "郑州": 719, "青岛": 703, "厦门": 682,
    "合肥": 664, "大连": 600, "宁波": 654, "无锡": 636,
    "东莞": 659, "济南": 702, "福州": 689, "沈阳": 599,
    "昆明": 756, "贵阳": 757, "南宁": 769, "哈尔滨": 603,
    "石家庄": 612, "太原": 616, "南昌": 691, "海口": 776,
    "兰州": 751, "银川": 772, "西宁": 855, "拉萨": 794,
}

# ---------------------------------------------------------------------------
# User-Agent 池（桌面端 Chrome / Firefox / Edge + 移动端）
# ---------------------------------------------------------------------------

_USER_AGENTS: list[str] = [
    # Chrome 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Edge 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Opera 桌面端
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/110.0.0.0",
    # Safari 桌面端
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Chrome 移动端
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.122 Mobile/15E148 Safari/604.1",
    # Safari 移动端
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

# 字体加密 Unicode 私有区模式
_FONT_ENCRYPTED_PATTERN = re.compile(r"[-]")

# 详情页描述选择器（按优先级排列）
_DETAIL_DESC_SELECTORS: list[str] = [
    ".describtion__detail-content",
    ".job-detail__description",
    ".job-description",
    "[class*='description']",
    "[class*='job-detail']",
    ".job-detail-box",
    "article",
    ".content",
]

# 详情页技能选择器
_DETAIL_SKILL_SELECTORS: list[str] = [
    ".job-tag",
    ".tag-list .tag",
    "[class*='skill'] [class*='tag']",
    ".job-detail__tags .tag",
    ".welfare-tag",
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class CrawlStats:
    """单次爬取任务的统计数据。"""

    keywords_count: int = 0
    cities_count: int = 0
    pages_crawled: int = 0
    jobs_found: int = 0
    details_fetched: int = 0
    details_success: int = 0
    added: int = 0
    skipped: int = 0
    failed_parse: int = 0
    failed_save: int = 0
    aiohttp_success: int = 0
    playwright_fallback: int = 0
    dom_fallback: int = 0
    start_time: str = ""
    end_time: str = ""

    @property
    def duration_seconds(self) -> float:
        """计算爬取耗时（秒）。"""
        if self.start_time and self.end_time:
            try:
                start = datetime.fromisoformat(self.start_time)
                end = datetime.fromisoformat(self.end_time)
                return (end - start).total_seconds()
            except Exception:
                pass
        return 0.0

    @property
    def success_rate(self) -> float:
        """计算入库成功率。"""
        total = self.added + self.skipped + self.failed_save
        return self.added / total * 100 if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["duration_seconds"] = self.duration_seconds
        result["success_rate"] = round(self.success_rate, 1)
        return result


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def decode_font_text(text: str | None) -> str:
    """剔除字体加密的 Unicode 私有区字符，压缩空白。"""
    if not text:
        return ""
    cleaned = _FONT_ENCRYPTED_PATTERN.sub("", str(text))
    return re.sub(r"\s+", " ", cleaned).strip()


def resolve_city_id(city: str) -> int:
    """将城市中文名解析为智联 cityId，未匹配时回退到北京(530)。"""
    name = city.strip().replace("市", "")
    if name in CITY_ID_MAP:
        return CITY_ID_MAP[name]
    for key, cid in CITY_ID_MAP.items():
        if key in name or name in key:
            return cid
    logger.warning("未找到城市 '%s' 的 cityId，默认使用北京(530)", city)
    return 530


def parse_keywords_arg(raw: str | list[str]) -> list[str]:
    """
    解析关键词参数，支持空格分隔和逗号分隔两种形式。

    Examples:
        >>> parse_keywords_arg("Python,Java,前端")
        ['Python', 'Java', '前端']
        >>> parse_keywords_arg(["Python", "Java"])
        ['Python', 'Java']
    """
    if isinstance(raw, list):
        result: list[str] = []
        for item in raw:
            result.extend(parse_keywords_arg(item))
        return result
    # 字符串：先按逗号分，再 trim
    parts = re.split(r"[,，]", str(raw))
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# 断点续爬管理器
# ---------------------------------------------------------------------------


class CheckpointManager:
    """管理爬取进度断点，支持跨会话续爬。"""

    def __init__(self, file_path: Path | None = None) -> None:
        if file_path is None:
            file_path = BASE_DIR / "data" / _CHECKPOINT_FILE
        self._file = file_path
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """从磁盘加载断点文件。"""
        if self._file.exists():
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(
                    "已加载断点文件: %s (共 %s 条记录)",
                    self._file,
                    len(self._data),
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("断点文件损坏，将重新创建: %s", exc)
                self._data = {}

    def _save(self) -> None:
        """将断点数据写入磁盘。"""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _make_key(self, city: str, keyword: str) -> str:
        """生成断点记录键。"""
        return f"{keyword}_{city}"

    def get_progress(self, city: str, keyword: str) -> int:
        """
        获取指定组合的最后完成页码。

        Returns:
            最后完成的页码，0 表示尚未开始。
        """
        entry = self._data.get(self._make_key(city, keyword))
        if entry:
            return entry.get("last_page", 0)
        return 0

    def update_progress(
        self, city: str, keyword: str, page: int, added: int
    ) -> None:
        """更新指定组合的爬取进度。"""
        key = self._make_key(city, keyword)
        existing = self._data.get(key, {})
        existing["last_page"] = page
        existing["total_added"] = existing.get("total_added", 0) + added
        existing["updated_at"] = datetime.now().isoformat()
        self._data[key] = existing
        self._save()

    def clear(self) -> None:
        """清空所有断点记录。"""
        self._data = {}
        if self._file.exists():
            self._file.unlink()
        logger.info("断点记录已清空")

    def summary(self) -> str:
        """返回断点摘要信息。"""
        if not self._data:
            return "暂无断点记录"
        lines = []
        total = 0
        for key, entry in sorted(self._data.items()):
            added = entry.get("total_added", 0)
            total += added
            lines.append(
                f"  {key}: 完成第{entry.get('last_page', 0)}页, "
                f"已入库{added}条"
            )
        lines.append(f"  总计已入库: {total} 条")
        return "\n".join(lines)


# ===========================================================================
# 异步智联爬虫（优化版）
# ===========================================================================


class AsyncZhilianCrawler:
    """
    异步高性能智联招聘爬虫（生产级优化版）。

    三级数据获取策略:
        1. aiohttp 直接请求 API（最快）
        2. Playwright 浏览器内 API 请求（中等速度，复用 Cookie）
        3. DOM 卡片解析兜底（最慢但最可靠）

    详情页补充策略:
        1. aiohttp 请求详情 API
        2. Playwright 打开职位详情页提取 description + skills（兜底）

    使用示例::

        crawler = AsyncZhilianCrawler(
            keywords=["Python", "Java"],
            cities=["北京", "上海"],
            max_pages=10,
            speed="normal",
        )
        stats = await crawler.run()
    """

    def __init__(
        self,
        keywords: list[str],
        cities: list[str],
        max_pages: int = 10,
        *,
        db: DatabaseManager | None = None,
        concurrency: int | None = None,
        min_delay: float | None = None,
        max_delay: float | None = None,
        speed: str = "normal",
        fetch_detail: bool = True,
        resume: bool = True,
        clear_checkpoint: bool = False,
    ) -> None:
        """
        Args:
            keywords: 搜索关键词列表。
            cities: 目标城市列表。
            max_pages: 每个组合最大爬取页数（上限 50）。
            db: 数据库管理器，默认使用全局 ``db_manager``。
            concurrency: 全局并发数（None 则由 speed 档位决定）。
            min_delay: 请求间最小延时/秒（None 则由 speed 决定）。
            max_delay: 请求间最大延时/秒（None 则由 speed 决定）。
            speed: 速度档位，``"fast"`` / ``"normal"`` / ``"safe"``。
            fetch_detail: 是否请求详情页补充描述与技能。
            resume: 是否启用断点续爬。
            clear_checkpoint: 启动前是否清空历史断点。
        """
        self.keywords = [k.strip() for k in keywords if k.strip()]
        self.cities = [c.strip() for c in cities if c.strip()]
        self.max_pages = max(1, min(max_pages, _MAX_PAGES_LIMIT))
        self._db = db or db_manager
        self.fetch_detail = fetch_detail
        self.resume = resume
        self.speed = speed if speed in _SPEED_PRESETS else "normal"

        # 速度档位：若未显式传入，则使用档位预设值
        preset = _SPEED_PRESETS[self.speed]
        self.concurrency = concurrency if concurrency is not None else preset[0]
        self.min_delay = min_delay if min_delay is not None else preset[1]
        self.max_delay = max_delay if max_delay is not None else preset[2]
        self._detail_concurrency = preset[3]

        # 限制并发上限
        self.concurrency = max(1, min(self.concurrency, 10))
        self._detail_concurrency = max(1, min(self._detail_concurrency, self.concurrency))

        self._cleaner = DataCleaner()
        self._checkpoint = CheckpointManager()

        if clear_checkpoint:
            self._checkpoint.clear()

        # 并发信号量
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(self.concurrency)
        self._detail_semaphore: asyncio.Semaphore = asyncio.Semaphore(
            self._detail_concurrency
        )

        # Cookie 管理
        self._cookies: str = ""
        self._cookie_timestamp: float = 0.0
        self._cookie_lock = asyncio.Lock()  # 防止并发刷新 Cookie
        self._consecutive_403: int = 0

        # aiohttp session
        self._session: ClientSession | None = None

        # Playwright 浏览器实例（复用，避免每次创建）
        self._playwright_browser: Any = None
        self._playwright_context: Any = None

        # 详情页共享浏览器（所有详情请求复用同一 Chromium 进程）
        self._detail_browser: Any = None
        self._detail_playwright: Any = None

        # 详情 API 连续 404 计数器（达到阈值后跳过所有详情 API 请求）
        self._detail_api_404_count: int = 0
        self._DETAIL_API_404_THRESHOLD: int = 5

        # 统计
        self._stats = CrawlStats()
        # 当前组合开始时间（用于单组合耗时统计）
        self._combo_start: float = 0.0

    # ==================================================================
    # Cookie 与 Session 管理
    # ==================================================================

    async def _ensure_cookies(self, force: bool = False) -> str:
        """
        确保 Cookie 有效。

        Cookie 过期（默认 20 分钟）或强制刷新时，通过 Playwright
        重新访问智联首页获取最新 Cookie。

        Args:
            force: 是否强制刷新（忽略时间间隔检查）。

        Returns:
            Cookie 字符串。
        """
        now = time.time()
        if not force and self._cookies and \
           (now - self._cookie_timestamp) < _COOKIE_REFRESH_INTERVAL:
            return self._cookies

        # 使用锁防止并发刷新
        async with self._cookie_lock:
            # 双重检查：可能其他协程已经刷新了
            if not force and self._cookies and \
               (now - self._cookie_timestamp) < _COOKIE_REFRESH_INTERVAL:
                return self._cookies

            logger.info("正在通过 Playwright 刷新 Cookie%s...",
                        "（强制）" if force else "")

            try:
                from playwright.async_api import async_playwright
            except ImportError:
                logger.warning("playwright 未安装，将使用空 Cookie")
                self._cookies = ""
                self._cookie_timestamp = now
                return self._cookies

            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                        ],
                    )
                    context = await browser.new_context(
                        user_agent=random.choice(_USER_AGENTS),
                        viewport={
                            "width": random.randint(1280, 1920),
                            "height": random.randint(720, 1080),
                        },
                        locale="zh-CN",
                        timezone_id="Asia/Shanghai",
                    )
                    page = await context.new_page()

                    # 注入反检测脚本
                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        window.chrome = { runtime: {} };
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['zh-CN', 'zh', 'en']
                        });
                    """)

                    await page.goto(
                        _SEARCH_PAGE_URL,
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    # 模拟人类浏览行为：滚动 + 等待
                    await page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight / 3)"
                    )
                    await page.wait_for_timeout(random.randint(2000, 4000))

                    cookies = await context.cookies()
                    self._cookies = "; ".join(
                        f"{c['name']}={c['value']}" for c in cookies
                    )

                    await context.close()
                    await browser.close()
            except Exception as exc:
                logger.warning("Cookie 刷新失败: %s", exc)
                if not self._cookies:
                    self._cookies = ""

            self._cookie_timestamp = time.time()
            self._consecutive_403 = 0
            logger.info("Cookie 刷新完成，长度=%s", len(self._cookies))
            return self._cookies

    def _build_headers(self, *, referer: str | None = None) -> dict[str, str]:
        """构建带随机 UA 与 Cookie 的多样化请求头。"""
        ua = random.choice(_USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": random.choice([
                "application/json, text/plain, */*",
                "application/json, text/javascript, */*; q=0.01",
            ]),
            "Accept-Language": random.choice([
                "zh-CN,zh;q=0.9,en;q=0.8",
                "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
                "zh-CN,zh;q=0.9",
            ]),
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Chromium";v="126", "Google Chrome";v="126", "Not?A_Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{random.choice(["Windows", "macOS", "Linux"])}"',
        }
        if self._cookies:
            headers["Cookie"] = self._cookies
        if referer:
            headers["Referer"] = referer
        return headers

    # ==================================================================
    # 异步延时
    # ==================================================================

    async def _random_delay(self, multiplier: float = 1.0) -> None:
        """
        随机异步延时，降低请求频率。

        Args:
            multiplier: 延时倍率（详情页调用时可适当加大）。
        """
        delay = random.uniform(
            self.min_delay * multiplier,
            self.max_delay * multiplier,
        )
        await asyncio.sleep(delay)

    # ==================================================================
    # API 请求核心
    # ==================================================================

    async def _fetch_json(
        self,
        url: str,
        *,
        referer: str | None = None,
        retries: int = 3,
        timeout: int = 30,
    ) -> dict[str, Any] | None:
        """
        异步请求 JSON API，带指数退避自动重试。

        遇到 403/429 时自动刷新 Cookie 后重试。

        Args:
            url: API 地址。
            referer: Referer 请求头。
            retries: 最大重试次数。
            timeout: 请求超时（秒）。

        Returns:
            解析后的 JSON 字典，失败返回 ``None``。
        """
        if self._session is None:
            raise RuntimeError("Session 未初始化，请先调用 run()")

        async with self._semaphore:
            for attempt in range(1, retries + 1):
                try:
                    headers = self._build_headers(referer=referer)
                    async with self._session.get(
                        url,
                        headers=headers,
                        timeout=ClientTimeout(total=timeout),
                    ) as resp:
                        if resp.status == 200:
                            self._consecutive_403 = 0
                            data: dict[str, Any] = await resp.json()
                            return data

                        elif resp.status in (403, 429):
                            self._consecutive_403 += 1
                            wait_time = min(
                                2 ** attempt + random.uniform(0, 3), 60
                            )
                            logger.warning(
                                "API 返回 %s，等待 %.1fs (第 %s/%s 次)",
                                resp.status, wait_time, attempt, retries,
                            )
                            # 连续 403 时强制刷新 Cookie
                            if self._consecutive_403 >= _COOKIE_FORCE_REFRESH_ON_ERRORS:
                                await self._ensure_cookies(force=True)
                            await asyncio.sleep(wait_time)
                        else:
                            logger.debug(
                                "API status=%s url=%s",
                                resp.status, url[:100],
                            )
                            if attempt < retries:
                                await asyncio.sleep(1.0 * attempt)

                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    logger.debug(
                        "API 请求异常 (第 %s/%s 次): %s",
                        attempt, retries, exc,
                    )
                    if attempt < retries:
                        await asyncio.sleep(1.5 * attempt)
                except Exception as exc:
                    logger.error("API 未知异常: %s", exc)
                    return None

            logger.debug("API 请求最终失败: %s", url[:120])
            return None

    # ==================================================================
    # 列表页获取（三级兜底）
    # ==================================================================

    async def _fetch_list_page(
        self,
        city_id: int,
        keyword: str,
        page: int,
    ) -> list[dict[str, Any]]:
        """
        获取单页职位列表（aiohttp 优先，Playwright 兜底）。

        Args:
            city_id: 智联城市 ID。
            keyword: 搜索关键词。
            page: 页码。

        Returns:
            职位条目列表。
        """
        start = (page - 1) * _PAGE_SIZE
        url = (
            f"{_API_HOST}{_API_SEARCH_PATH}"
            f"?start={start}"
            f"&pageSize={_PAGE_SIZE}"
            f"&cityId={city_id}"
            f"&workExperience=-1"
            f"&education=-1"
            f"&companyType=-1"
            f"&employmentType=-1"
            f"&jobWelfareTag=-1"
            f"&kw={quote(keyword)}"
            f"&kt=3"
        )

        # ---- 方式一：aiohttp 直接请求 API ----
        await self._random_delay()
        data = await self._fetch_json(url, referer=_SEARCH_PAGE_URL)

        if data:
            results = self._extract_results(data)
            if results:
                self._stats.aiohttp_success += 1
                logger.debug(
                    "[aiohttp] city=%s kw=%s page=%s → %s 条",
                    city_id, keyword, page, len(results),
                )
                return results

        # ---- 方式二：Playwright 浏览器兜底 ----
        logger.info("aiohttp 未获取到数据，启用 Playwright 兜底...")
        results = await self._fetch_list_via_playwright(city_id, keyword, page)
        if results:
            self._stats.playwright_fallback += 1
            logger.debug(
                "[playwright] city=%s kw=%s page=%s → %s 条",
                city_id, keyword, page, len(results),
            )
        return results

    async def _fetch_list_via_playwright(
        self,
        city_id: int,
        keyword: str,
        page: int,
    ) -> list[dict[str, Any]]:
        """
        通过 Playwright 浏览器获取列表数据。

        1. 浏览器内请求 API（复用 Cookie 上下文）
        2. DOM 卡片解析（最终兜底）

        Args:
            city_id: 智联城市 ID。
            keyword: 搜索关键词。
            page: 页码。

        Returns:
            职位条目列表。
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright 未安装，无法使用浏览器兜底")
            return []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                context = await browser.new_context(
                    user_agent=random.choice(_USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                )
                page_obj = await context.new_page()

                # 注入反检测
                await page_obj.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                """)

                # 访问搜索首页建立 Cookie
                await page_obj.goto(
                    _SEARCH_PAGE_URL,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                await page_obj.wait_for_timeout(random.randint(1000, 2000))

                # 策略一：浏览器内直接请求 API
                captured: list[dict[str, Any]] = []
                start = (page - 1) * _PAGE_SIZE
                api_url = (
                    f"{_API_HOST}{_API_SEARCH_PATH}"
                    f"?start={start}&pageSize={_PAGE_SIZE}"
                    f"&cityId={city_id}"
                    f"&workExperience=-1&education=-1&companyType=-1"
                    f"&employmentType=-1&jobWelfareTag=-1"
                    f"&kw={quote(keyword)}&kt=3"
                )
                try:
                    resp = await page_obj.request.get(
                        api_url,
                        headers={
                            "User-Agent": random.choice(_USER_AGENTS),
                            "Referer": _SEARCH_PAGE_URL,
                            "Accept": "application/json, text/plain, */*",
                        },
                    )
                    if resp.ok:
                        payload = await resp.json()
                        captured = self._extract_results(payload)
                except Exception as exc:
                    logger.debug("浏览器 API 请求异常: %s", exc)

                # 策略二：DOM 解析兜底
                if not captured:
                    captured = await self._parse_dom_cards(page_obj)
                    if captured:
                        self._stats.dom_fallback += 1

                await context.close()
                await browser.close()
                return captured

        except Exception as exc:
            logger.warning("Playwright 兜底异常: %s", exc)
            return []

    async def _parse_dom_cards(self, page_obj: Any) -> list[dict[str, Any]]:
        """
        DOM 解析搜索结果页的职位卡片。

        Args:
            page_obj: Playwright Page 对象。

        Returns:
            解析出的职位条目列表。
        """
        items: list[dict[str, Any]] = []
        selectors = [
            ".joblist-box__item",
            ".positionlist__item",
            ".jobList .job_item",
            "[class*='joblist'] [class*='item']",
            "[class*='jobList'] [class*='item']",
        ]

        cards = []
        for selector in selectors:
            try:
                cards = await page_obj.query_selector_all(selector)
            except Exception:
                continue
            if cards:
                break

        for card in cards[:30]:
            try:
                title_el = await card.query_selector(
                    "a[href*='jobdetail'], .jobinfo__name, .job-name, [class*='jobTitle'], [class*='job-title']"
                )
                company_el = await card.query_selector(
                    ".companyinfo__name, .company-name, .company__name, [class*='companyName'], [class*='company-name']"
                )
                salary_el = await card.query_selector(
                    ".jobinfo__salary, .salary, [class*='salary']"
                )
                city_el = await card.query_selector(
                    ".jobinfo__area, .job-area, [class*='area']"
                )
                exp_el = await card.query_selector(
                    ".jobinfo__exp, [class*='experience']"
                )
                edu_el = await card.query_selector(
                    ".jobinfo__edu, [class*='education']"
                )

                if not title_el:
                    continue

                title = decode_font_text(await title_el.inner_text())
                company = decode_font_text(
                    await company_el.inner_text() if company_el else "未知公司"
                )
                salary = decode_font_text(
                    await salary_el.inner_text() if salary_el else ""
                )
                city_text = decode_font_text(
                    await city_el.inner_text() if city_el else ""
                )
                experience = decode_font_text(
                    await exp_el.inner_text() if exp_el else ""
                )
                education = decode_font_text(
                    await edu_el.inner_text() if edu_el else ""
                )

                href = await title_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = f"https://www.zhaopin.com{href}"

                # 从 href 中提取 number
                number = ""
                match = re.search(r"jobdetail/([A-Za-z0-9]+)", href)
                if match:
                    number = match.group(1)

                items.append({
                    "jobName": title,
                    "companyName": company,
                    "salary": salary,
                    "city": {"display": city_text} if city_text else {},
                    "workingExp": {"name": experience} if experience else {},
                    "eduLevel": {"name": education} if education else {},
                    "positionURL": href,
                    "number": number,
                })
            except Exception:
                continue

        if items:
            logger.info("DOM 兜底解析到 %s 条职位", len(items))
        return items

    # ==================================================================
    # 详情页获取（Playwright 深度抓取）
    # ==================================================================

    async def _fetch_detail(self, number: str) -> dict[str, Any] | None:
        """
        获取职位详情（仅 aiohttp API）。

        注意：Playwright 详情页兜底已禁用 —— 智联详情页受腾讯 EdgeOne
        安全防护，headless 浏览器会被拦截。详情数据通过搜索页 DOM 和
        标题关键词提取补充。

        Args:
            number: 职位编号。

        Returns:
            详情数据字典，失败返回 ``None``。
        """
        # 连续 404 过多时，快速跳过后续所有详情请求
        if self._detail_api_404_count >= self._DETAIL_API_404_THRESHOLD:
            return None

        url = f"{_API_HOST}{_API_DETAIL_PATH}?number={number}"

        async with self._detail_semaphore:
            await self._random_delay(multiplier=1.5)
            data = await self._fetch_json(
                url, referer=_SEARCH_PAGE_URL, timeout=15, retries=1,
            )

            if data:
                # 重置计数器（有正常响应）
                self._detail_api_404_count = 0
                detail = data.get("data") or {}
                if detail.get("jobDetail") or detail.get("description"):
                    self._stats.details_success += 1
                    return detail
                return None

            # API 返回 None（含 404），累加计数
            self._detail_api_404_count += 1
            if self._detail_api_404_count == self._DETAIL_API_404_THRESHOLD:
                logger.info(
                    "详情 API 连续 %s 次失败，后续将跳过所有详情请求（节省时间）",
                    self._detail_api_404_count,
                )
            return None

    async def _ensure_detail_browser(self) -> tuple[Any, Any]:
        """
        懒加载共享浏览器实例，所有详情页复用同一个 browser。

        返回 (browser, playwright_instance)，browser 用于创建独立 context。

        Returns:
            (browser, playwright) 元组。
        """
        if self._detail_browser is not None:
            return self._detail_browser, self._detail_playwright

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("playwright 未安装")

        self._detail_playwright = await async_playwright().start()
        self._detail_browser = await self._detail_playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        logger.debug("详情共享浏览器已启动")
        return self._detail_browser, self._detail_playwright

    async def _fetch_detail_via_playwright(
        self, number: str
    ) -> dict[str, Any] | None:
        """
        通过 Playwright 打开职位详情页，从 DOM 提取描述和技能。

        复用共享浏览器实例，每个详情页仅创建独立的 context/page，
        大幅降低资源开销（不再每次启动新 Chromium）。

        Args:
            number: 职位编号。

        Returns:
            含 description / skills 的字典，失败返回 ``None``。
        """
        try:
            browser, _ = await self._ensure_detail_browser()
        except RuntimeError:
            return None

        detail_url = _DETAIL_PAGE_URL.format(number=number)
        context = None

        try:
            context = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            page_obj = await context.new_page()

            # 反检测脚本
            await page_obj.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
            """)

            # 访问详情页
            await page_obj.goto(
                detail_url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            await page_obj.wait_for_timeout(random.randint(1000, 2000))

            # 滚动触发懒加载
            await page_obj.evaluate(
                "window.scrollTo(0, document.body.scrollHeight / 2)"
            )
            await page_obj.wait_for_timeout(300)

            result: dict[str, Any] = {}

            # ---- 提取描述 ----
            description = ""
            for selector in _DETAIL_DESC_SELECTORS:
                try:
                    el = await page_obj.query_selector(selector)
                    if el:
                        text = await el.inner_text()
                        text = decode_font_text(text)
                        if text and len(text) > 20:
                            description = text
                            break
                except Exception:
                    continue

            if description:
                result["jobDetail"] = description
                result["description"] = description

            # ---- 提取技能标签 ----
            skills: list[str] = []
            for selector in _DETAIL_SKILL_SELECTORS:
                try:
                    els = await page_obj.query_selector_all(selector)
                    for el in els:
                        tag = decode_font_text(await el.inner_text())
                        if tag and len(tag) < 30 and tag not in skills:
                            skills.append(tag)
                except Exception:
                    continue

            if skills:
                result["skillLabel"] = skills

            if description or skills:
                self._stats.details_success += 1
                logger.debug(
                    "详情页提取成功: number=%s desc_len=%s skills=%s",
                    number, len(description), len(skills),
                )
                return result

            return None

        except Exception as exc:
            logger.debug("详情页 Playwright 提取异常 number=%s: %s", number, exc)
            return None
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass

    # ==================================================================
    # 数据提取与解析
    # ==================================================================

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

    def _parse_salary(
        self, salary_text: str | None
    ) -> tuple[float | None, float | None]:
        """解析薪资文本为 (min, max)，单位 K/月。"""
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

        # positionLabel 中的 jobLight JSON
        label_raw = item.get("positionLabel")
        if isinstance(label_raw, str) and "jobLight" in label_raw:
            match = re.search(r'"jobLight"\s*:\s*\[(.*?)\]', label_raw, re.S)
            if match:
                parts = re.findall(r'"([^"]+)"', match.group(1))
                skills.extend(parts)

        keyword = item.get("keyword")
        if isinstance(keyword, str) and keyword.strip():
            skills.extend(re.split(r"[,，\s]+", keyword))

        # 从 description 中提取常见技术关键词作为兜底技能
        desc = item.get("jobDetail") or item.get("description") or ""
        if isinstance(desc, str) and not skills:
            tech_keywords = [
                "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust",
                "C++", "React", "Vue", "Angular", "Node.js", "Django",
                "Flask", "Spring", "MySQL", "PostgreSQL", "MongoDB", "Redis",
                "Docker", "Kubernetes", "AWS", "Linux", "Git", "SQL",
                "HTML", "CSS", "机器学习", "深度学习", "数据分析",
                "人工智能", "大数据", "Hadoop", "Spark", "Flink",
            ]
            desc_lower = desc.lower()
            for kw in tech_keywords:
                if kw.lower() in desc_lower:
                    skills.append(kw)

        skills = [decode_font_text(s) for s in skills if s]
        skills = list(dict.fromkeys(s for s in skills if s))
        return skills or None

    def _parse_job_item(
        self,
        item: dict[str, Any],
        detail: dict[str, Any] | None = None,
        search_city: str = "",
    ) -> dict[str, Any] | None:
        """
        将单条职位数据转换为入库字典。

        优先从详情数据补充 description 与 skills。

        Args:
            item: 列表 API / DOM 解析返回的职位条目。
            detail: 详情 API / Playwright 详情页返回的数据。
            search_city: 搜索城市名，当 API 返回空城市时作为兜底值。

        Returns:
            标准化职位字典；必填字段缺失时返回 ``None``。
        """
        # --- 基本信息 ---
        title = decode_font_text(
            item.get("jobName")
            or item.get("name")
            or item.get("positionName")
        )
        company_info = item.get("company") or {}
        company = decode_font_text(
            item.get("companyName")
            or (company_info.get("name") if isinstance(company_info, dict) else None)
            or item.get("companyNameWithoutFormat")
        )

        # --- 城市 ---
        city_info = item.get("city") or {}
        city_display = (
            city_info.get("display")
            if isinstance(city_info, dict)
            else item.get("cityName")
        )
        city_name = decode_font_text(city_display) or ""
        # API 返回空城市时，使用搜索城市兜底（搜索结果是按城市筛选的）
        if not city_name and search_city:
            city_name = search_city
        if not city_name:
            city_name = "未知"

        district = None
        if isinstance(city_info, dict):
            district = decode_font_text(
                city_info.get("district") or city_info.get("areaDistrict")
            )

        # --- 薪资 ---
        salary_raw = decode_font_text(item.get("salary"))
        salary_min, salary_max = self._parse_salary(salary_raw)

        # --- 经验 ---
        exp_info = item.get("workingExp") or item.get("workExperience") or {}
        experience = decode_font_text(
            exp_info.get("name")
            if isinstance(exp_info, dict)
            else item.get("experience")
        )

        # --- 学历 ---
        edu_info = item.get("eduLevel") or item.get("education") or {}
        education = decode_font_text(
            edu_info.get("name")
            if isinstance(edu_info, dict)
            else item.get("education")
        )

        # --- 行业 ---
        industry_info = (
            item.get("industryType") or company_info.get("industry") or {}
        )
        industry = decode_font_text(
            industry_info.get("name")
            if isinstance(industry_info, dict)
            else item.get("industry")
        )

        # --- 公司属性 ---
        company_size_info = (
            company_info.get("size") if isinstance(company_info, dict) else {}
        )
        company_size = (
            company_size_info.get("name")
            if isinstance(company_size_info, dict)
            else None
        )
        company_type_info = (
            company_info.get("type") if isinstance(company_info, dict) else {}
        )
        company_type = (
            company_type_info.get("name")
            if isinstance(company_type_info, dict)
            else None
        )

        # --- 描述（优先使用详情数据） ---
        description = decode_font_text(
            item.get("jobSummary")
            or item.get("jobDescribe")
            or item.get("description")
        )
        if detail:
            detail_desc = decode_font_text(
                detail.get("jobDetail")
                or detail.get("description")
                or detail.get("jobDescribe")
            )
            if detail_desc:
                description = detail_desc

        # --- 技能（合并列表与详情中的技能） ---
        skills = self._parse_skills(item)
        if detail:
            detail_skills = self._parse_skills(detail)
            if detail_skills:
                if skills:
                    skills = list(dict.fromkeys(skills + detail_skills))
                else:
                    skills = detail_skills

        # --- URL 和编号 ---
        url = item.get("positionURL") or item.get("positionUrl") or item.get("url")
        number = item.get("number")
        if not url and number:
            url = _DETAIL_PAGE_URL.format(number=number)

        # --- 验证 ---
        if not title or not company:
            return None

        return {
            "title": title[:200],
            "company": company[:200],
            "city": (city_name or "未知")[:50],
            "district": district[:50] if district else None,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "experience": experience[:50] if experience else None,
            "education": education[:50] if education else None,
            "skills": skills,
            "company_size": (
                decode_font_text(company_size)[:50] if company_size else None
            ),
            "company_type": (
                decode_font_text(company_type)[:50] if company_type else None
            ),
            "industry": (
                decode_font_text(industry)[:100] if industry else None
            ),
            "description": description,
            "url": str(url)[:500] if url else None,
            "source": SOURCE_ZHILIAN,
            "is_simulated": False,
        }

    # ==================================================================
    # 清洗与入库
    # ==================================================================

    def _clean_and_save(self, job_data: dict[str, Any]) -> bool:
        """
        清洗单条职位数据并入库。

        Args:
            job_data: 原始职位字典。

        Returns:
            ``True`` 表示入库成功（含新增），``False`` 表示跳过或失败。
        """
        try:
            cleaned = self._cleaner.clean_job(job_data)
        except Exception as exc:
            logger.debug("清洗失败，使用原始数据入库: %s", exc)
            cleaned = job_data

        try:
            job_id = self._db.add_job(cleaned)
            if job_id is None:
                self._stats.skipped += 1
                return False
            else:
                self._stats.added += 1
                return True
        except Exception as exc:
            self._stats.failed_save += 1
            logger.error("入库失败 '%s': %s", cleaned.get("title", "?"), exc)
            return False

    # ==================================================================
    # 单组合爬取（核心循环）
    # ==================================================================

    async def _crawl_city_keyword(
        self,
        city: str,
        keyword: str,
    ) -> dict[str, int]:
        """
        爬取指定城市 + 关键词组合的所有页面。

        流程：
            列表页 → 解析基础字段 → 并发获取详情 → 清洗入库 → 更新断点

        Args:
            city: 城市中文名。
            keyword: 搜索关键词。

        Returns:
            统计字典 ``{"added": N, "skipped": N, "failed": N, "pages": N}``。
        """
        city_id = resolve_city_id(city)
        start_page = 1
        added_before = self._stats.added
        self._combo_start = time.time()

        # 断点续爬
        if self.resume:
            last_page = self._checkpoint.get_progress(city, keyword)
            if last_page > 0:
                logger.info(
                    "↳ 断点续爬: %s @ %s 已完成 %s 页，从第 %s 页继续",
                    keyword, city, last_page, last_page + 1,
                )
                start_page = last_page + 1

        if start_page > self.max_pages:
            logger.info("↳ %s @ %s 已全部完成，跳过", keyword, city)
            return {"added": 0, "skipped": 0, "failed": 0, "pages": 0}

        logger.info(
            "▶ [%s @ %s] cityId=%s 第 %s-%s 页",
            keyword, city, city_id, start_page, self.max_pages,
        )

        combo_pages = 0
        combo_added = 0
        combo_skipped = 0
        combo_failed = 0

        for page in range(start_page, self.max_pages + 1):
            # --- 1. 获取列表页 ---
            items = await self._fetch_list_page(city_id, keyword, page)

            if not items:
                if page > start_page:
                    logger.info(
                        "  第 %s 页无数据，翻页结束 [%s @ %s]",
                        page, keyword, city,
                    )
                else:
                    logger.warning(
                        "  第 %s 页（首页）无数据: %s @ %s", page, keyword, city,
                    )
                break

            self._stats.jobs_found += len(items)
            self._stats.pages_crawled += 1
            combo_pages += 1

            # --- 2. 解析基础数据 + 标记需详情的条目 ---
            parsed_jobs: list[dict[str, Any]] = []
            detail_tasks_info: list[tuple[int, str]] = []

            for idx, item in enumerate(items):
                job_data = self._parse_job_item(item, search_city=city)
                if not job_data:
                    self._stats.failed_parse += 1
                    continue

                parsed_jobs.append(job_data)

                if self.fetch_detail:
                    number = item.get("number")
                    # 没有 description 或没有 skills 时都尝试获取详情
                    need_detail = (
                        not job_data.get("description")
                        or not job_data.get("skills")
                    )
                    if number and need_detail:
                        detail_tasks_info.append(
                            (len(parsed_jobs) - 1, str(number))
                        )

            # --- 3. 并发获取详情页 ---
            if detail_tasks_info:
                self._stats.details_fetched += len(detail_tasks_info)

                detail_tasks = [
                    self._fetch_detail(number)
                    for _, number in detail_tasks_info
                ]
                detail_results = await asyncio.gather(
                    *detail_tasks, return_exceptions=True
                )

                enrich_count = 0
                for (job_idx, _), detail_result in zip(
                    detail_tasks_info, detail_results
                ):
                    if isinstance(detail_result, Exception):
                        continue
                    if detail_result is None:
                        continue

                    original_item = (
                        items[job_idx] if job_idx < len(items) else {}
                    )
                    enriched = self._parse_job_item(
                        original_item, detail=detail_result, search_city=city
                    )
                    if enriched:
                        parsed_jobs[job_idx] = enriched
                        enrich_count += 1

                if enrich_count:
                    logger.debug(
                        "  详情补充: %s/%s 条成功",
                        enrich_count, len(detail_tasks_info),
                    )

            # --- 4. 清洗并入库 ---
            page_added = 0
            for job_data in parsed_jobs:
                success = self._clean_and_save(job_data)
                if success:
                    page_added += 1
                else:
                    combo_skipped += 1

            combo_added += page_added

            # --- 5. 更新断点 ---
            if self.resume:
                self._checkpoint.update_progress(
                    city, keyword, page, page_added,
                )

            # --- 6. 进度日志 ---
            elapsed = time.time() - self._combo_start
            logger.info(
                "  第%s页: 发现%s条 → 新增%s条 | 累计%s条 | 耗时%.0fs [%s @ %s]",
                page, len(items), page_added,
                self._stats.added, elapsed, keyword, city,
            )

            # 页间延时
            if page < self.max_pages:
                await asyncio.sleep(random.uniform(1.5, 3.0))

        # 组合完成总结
        elapsed = time.time() - self._combo_start
        total_new = self._stats.added - added_before
        logger.info(
            "✔ [%s @ %s] 完成 | 翻页%s | 新增%s | 累计%s | 耗时%.0fs",
            keyword, city, combo_pages, total_new,
            self._stats.added, elapsed,
        )

        return {
            "added": combo_added,
            "skipped": combo_skipped,
            "failed": combo_failed,
            "pages": combo_pages,
        }

    # ==================================================================
    # 主入口
    # ==================================================================

    async def run(self) -> CrawlStats:
        """
        执行完整的异步爬取任务。

        Returns:
            包含详细统计信息的 ``CrawlStats`` 对象。
        """
        self._stats = CrawlStats(
            keywords_count=len(self.keywords),
            cities_count=len(self.cities),
            start_time=datetime.now().isoformat(),
        )

        total_combos = len(self.keywords) * len(self.cities)

        # ---- 启动 Banner ----
        logger.info("=" * 64)
        logger.info("  智联招聘异步高性能爬虫 v2.0 (生产级优化版)")
        logger.info("=" * 64)
        logger.info("  关键词 (%s): %s", len(self.keywords), ", ".join(self.keywords))
        logger.info("  城市   (%s): %s", len(self.cities), ", ".join(self.cities))
        logger.info("  组合数: %s | 每组合最多 %s 页", total_combos, self.max_pages)
        logger.info(
            "  并发: %s | 延时: %.1f-%.1fs | 详情并发: %s | 速度: %s",
            self.concurrency, self.min_delay, self.max_delay,
            self._detail_concurrency, self.speed,
        )
        logger.info("  详情抓取: %s | 断点续爬: %s", self.fetch_detail, self.resume)

        if self.resume:
            logger.info("  --- 断点状态 ---")
            for line in self._checkpoint.summary().split("\n"):
                logger.info("  %s", line)

        logger.info("=" * 64)

        # ---- 获取 Cookie ----
        await self._ensure_cookies()

        # ---- 创建 aiohttp Session ----
        connector = TCPConnector(
            limit=self.concurrency * 2,
            limit_per_host=self.concurrency,
            ttl_dns_cache=300,
            ssl=False,
        )
        timeout = ClientTimeout(total=30, connect=10)

        async with ClientSession(
            connector=connector,
            timeout=timeout,
        ) as session:
            self._session = session

            combo_index = 0
            for city in self.cities:
                for keyword in self.keywords:
                    combo_index += 1

                    # 定时刷新 Cookie
                    await self._ensure_cookies()

                    logger.info(
                        "━━ [%s/%s] %s @ %s ━━",
                        combo_index, total_combos, keyword, city,
                    )

                    try:
                        result = await self._crawl_city_keyword(city, keyword)
                    except KeyboardInterrupt:
                        logger.warning(
                            "用户中断！当前进度已保存 [%s @ %s]", keyword, city,
                        )
                        raise
                    except Exception as exc:
                        logger.exception(
                            "组合 [%s @ %s] 异常，跳过: %s", keyword, city, exc,
                        )

                    # 组合间休息（切换关键词/城市时稍长延时）
                    if combo_index < total_combos:
                        rest = random.uniform(3.0, 6.0)
                        logger.debug("组合间休息 %.1fs...", rest)
                        await asyncio.sleep(rest)

        self._stats.end_time = datetime.now().isoformat()

        # ---- 清理共享浏览器资源 ----
        if self._detail_browser is not None:
            try:
                await self._detail_browser.close()
            except Exception:
                pass
            self._detail_browser = None
        if self._detail_playwright is not None:
            try:
                await self._detail_playwright.stop()
            except Exception:
                pass
            self._detail_playwright = None

        self._log_final_report()
        return self._stats

    def _log_final_report(self) -> None:
        """输出详细的最终统计报告。"""
        duration = self._stats.duration_seconds
        if duration > 3600:
            dur_str = f"{duration / 3600:.1f} 小时"
        elif duration > 60:
            dur_str = f"{duration / 60:.1f} 分钟"
        else:
            dur_str = f"{duration:.0f} 秒"

        logger.info("")
        logger.info("╔" + "═" * 62 + "╗")
        logger.info("║  爬取任务 - 最终统计报告" + " " * 37 + "║")
        logger.info("╠" + "═" * 62 + "╣")
        logger.info("║  📊 数据概览" + " " * 50 + "║")
        logger.info("║    关键词数: %-5s  城市数: %-5s  总组合: %-5s ║",
                     self._stats.keywords_count, self._stats.cities_count,
                     self._stats.keywords_count * self._stats.cities_count)
        logger.info("║    翻页数: %-5s  发现职位: %-6s  详情请求: %-5s ║",
                     self._stats.pages_crawled, self._stats.jobs_found,
                     self._stats.details_fetched)
        logger.info("║    详情成功: %-5s" + " " * 46 + "║",
                     self._stats.details_success)
        logger.info("║" + " " * 62 + "║")
        logger.info("║  📥 入库统计" + " " * 50 + "║")
        logger.info("║    新增: %-6s  跳过(重复): %-5s  解析失败: %-5s ║",
                     self._stats.added, self._stats.skipped,
                     self._stats.failed_parse)
        logger.info("║    入库失败: %-5s  成功率: %.1f%%" + " " * 36 + "║",
                     self._stats.failed_save, self._stats.success_rate)
        logger.info("║" + " " * 62 + "║")
        logger.info("║  🔧 技术统计" + " " * 50 + "║")
        logger.info("║    aiohttp成功: %-3s  Playwright兜底: %-3s  DOM兜底: %-3s ║",
                     self._stats.aiohttp_success, self._stats.playwright_fallback,
                     self._stats.dom_fallback)
        logger.info("║    速度档位: %-8s  并发数: %-5s" + " " * 26 + "║",
                     self.speed, self.concurrency)
        logger.info("║" + " " * 62 + "║")
        logger.info("║  ⏱  耗时: %s" + " " * (54 - len(dur_str)) + "║", dur_str)
        logger.info("╚" + "═" * 62 + "╝")
        logger.info("")
        logger.info("数据存放: MySQL > job_analysis.jobs 表")
        logger.info("断点文件: %s", BASE_DIR / "data" / _CHECKPOINT_FILE)


# ===========================================================================
# 命令行入口
# ===========================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="异步高性能智联招聘爬虫 v2.0（生产级优化版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "速度档位说明:\n"
            "  fast   并发=8  延时=0.5-1.5s  适合快速测试\n"
            "  normal 并发=6  延时=1.0-3.0s  日常使用（默认）\n"
            "  safe   并发=4  延时=2.0-5.0s  大规模稳定采集\n\n"
            "示例:\n"
            "  # 单关键词单城市，快速模式\n"
            "  python crawler/async_zhilian_crawler.py -k Python -c 北京 --speed fast\n\n"
            "  # 多关键词（逗号分隔）+ 多城市\n"
            '  python crawler/async_zhilian_crawler.py -k "Python,Java,前端" -c 北京 上海 深圳\n\n'
            "  # 大规模爬取\n"
            "  python crawler/async_zhilian_crawler.py -k Python -c 北京 -p 15 -n 8 --speed safe\n\n"
            "  # 清空断点重新开始\n"
            "  python crawler/async_zhilian_crawler.py -k Python -c 北京 --clear-checkpoint\n\n"
            "  # 不抓详情（快速模式）\n"
            "  python crawler/async_zhilian_crawler.py -k Python -c 北京 --no-detail\n"
        ),
    )
    parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        default=["Python"],
        help="搜索关键词，支持空格或逗号分隔（默认: Python）。"
             ' 例: -k "Python,Java,前端" 或 -k Python Java 前端',
    )
    parser.add_argument(
        "-c", "--cities",
        nargs="+",
        default=["北京"],
        help="目标城市列表（默认: 北京）。例: -c 北京 上海 深圳",
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=10,
        help="每个组合的最大爬取页数（默认: 10，上限 50）",
    )
    parser.add_argument(
        "-n", "--concurrency",
        type=int,
        default=None,
        help="全局并发请求数（默认: 由 --speed 决定，手动指定后覆盖速度档位）",
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        nargs=2,
        default=None,
        metavar=("MIN", "MAX"),
        help="请求间随机延时范围/秒（默认: 由 --speed 决定）",
    )
    parser.add_argument(
        "--speed",
        choices=["fast", "normal", "safe"],
        default="normal",
        help="速度档位（fast/normal/safe），自动设置并发和延时。默认: normal",
    )
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="跳过详情页抓取（仅获取列表基础信息，速度更快但数据不完整）",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="禁用断点续爬，每次从头开始",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="启动前清空历史断点记录",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出 DEBUG 级别详细日志",
    )
    return parser.parse_args(argv)


def setup_logging(level: int = logging.INFO) -> None:
    """配置日志格式。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%m-%d %H:%M:%S",
    )


async def _async_main(argv: list[str] | None = None) -> int:
    """异步主入口。"""
    args = parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    # 解析关键词（支持逗号分隔）
    keywords = parse_keywords_arg(args.keywords)
    cities = [c.strip() for c in args.cities if c.strip()]

    # 构建爬虫实例
    crawler_kwargs: dict[str, Any] = dict(
        keywords=keywords,
        cities=cities,
        max_pages=min(args.max_pages, _MAX_PAGES_LIMIT),
        speed=args.speed,
        fetch_detail=not args.no_detail,
        resume=not args.no_resume,
        clear_checkpoint=args.clear_checkpoint,
    )

    # 手动指定并发/延时则覆盖速度档位
    if args.concurrency is not None:
        crawler_kwargs["concurrency"] = args.concurrency
    if args.delay is not None:
        crawler_kwargs["min_delay"] = args.delay[0]
        crawler_kwargs["max_delay"] = args.delay[1]

    # 检查 playwright 可用性
    try:
        import playwright  # noqa: F401
    except ImportError:
        logger.warning(
            "playwright 未安装，详情页深度抓取将不可用。"
            "安装: pip install playwright && playwright install chromium"
        )

    crawler = AsyncZhilianCrawler(**crawler_kwargs)

    try:
        stats = await crawler.run()
    except KeyboardInterrupt:
        logger.warning("⚠ 用户中断，当前进度已自动保存至断点文件")
        return 130
    except Exception as exc:
        logger.exception("爬取任务异常终止: %s", exc)
        return 1

    if stats.added == 0 and stats.pages_crawled == 0:
        logger.error(
            "未成功爬取任何数据。请检查:\n"
            "  1. 网络连接是否正常\n"
            "  2. Docker MySQL 是否运行: docker ps | grep mysql\n"
            "  3. 智联网站是否可访问: curl -I https://sou.zhaopin.com/\n"
            "  4. 尝试 --verbose 查看详细日志\n"
            "  5. 尝试 --speed fast 使用更快但更激进的策略"
        )
        return 2

    return 0


def main(argv: list[str] | None = None) -> int:
    """同步包装器，供命令行直接调用。"""
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
