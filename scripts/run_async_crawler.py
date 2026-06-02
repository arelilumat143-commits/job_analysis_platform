#!/usr/bin/env python3
"""
异步高性能爬虫启动脚本（v2 优化版）。

提供预设的批量爬取任务配置，一键启动多关键词、多城市的并行爬取。
同时支持命令行参数覆盖默认值。

使用示例::

    # 使用默认配置运行（5个关键词 × 5个城市，normal 档位）
    python scripts/run_async_crawler.py

    # 自定义关键词（支持逗号分隔）和城市
    python scripts/run_async_crawler.py -k Python,Java,前端 -c 北京,上海,深圳

    # 快速模式（speed=fast，不抓详情）
    python scripts/run_async_crawler.py --quick

    # 大规模爬取（15页/组合，speed=fast，更多关键词/城市）
    python scripts/run_async_crawler.py --large

    # 安全模式（低速高隐匿，适合长时间挂机）
    python scripts/run_async_crawler.py --speed safe -p 20

    # 增量更新（只爬新数据，不清断点）
    python scripts/run_async_crawler.py --incremental

    # 调试模式
    python scripts/run_async_crawler.py -k Python -c 北京 -p 1 --speed fast -v
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录加入模块路径
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from crawler.async_zhilian_crawler import (
    AsyncZhilianCrawler,
    parse_keywords_arg,
    setup_logging,
)

# ---------------------------------------------------------------------------
# 预设配置
# ---------------------------------------------------------------------------

# 热门技术岗位关键词
DEFAULT_KEYWORDS: list[str] = [
    "Python",
    "Java",
    "前端",
    "数据分析师",
    "产品经理",
]

# 一线/新一线城市
DEFAULT_CITIES: list[str] = [
    "北京",
    "上海",
    "深圳",
    "广州",
    "杭州",
]

# 大规模爬取关键词（覆盖更广的岗位类型）
LARGE_KEYWORDS: list[str] = [
    "Python",
    "Java",
    "前端",
    "数据分析师",
    "产品经理",
    "测试工程师",
    "运维",
    "UI设计师",
    "算法工程师",
    "C++",
]

# 大规模爬取城市
LARGE_CITIES: list[str] = [
    "北京",
    "上海",
    "深圳",
    "广州",
    "杭州",
    "成都",
    "武汉",
    "南京",
    "西安",
    "苏州",
]


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="异步高性能爬虫一键启动脚本（v2 优化版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "预设模式:\n"
            "  --quick        快速模式（3页，不抓详情，speed=fast）\n"
            "  --large        大规模模式（15页，抓详情，speed=fast，更多关键词/城市）\n"
            "  --incremental  增量模式（不清断点，只爬新数据）\n\n"
            "速度档位 (--speed):\n"
            "  fast    并发8，延时0.5-1.5s，适合快速测试\n"
            "  normal  并发6，延时1.0-3.0s（默认）\n"
            "  safe    并发4，延时2.0-5.0s，高隐匿长时间挂机\n\n"
            "自定义示例:\n"
            "  python scripts/run_async_crawler.py -k Python -c 北京 -p 10 --speed fast\n"
            "  python scripts/run_async_crawler.py -k Go,Rust,Kotlin -c 北京,上海 -p 5\n"
        ),
    )
    parser.add_argument(
        "-k",
        "--keywords",
        nargs="+",
        default=None,
        help="搜索关键词（空格或逗号分隔，默认使用预设热门关键词）",
    )
    parser.add_argument(
        "-c",
        "--cities",
        nargs="+",
        default=None,
        help="目标城市列表（默认使用预设一线城市）",
    )
    parser.add_argument(
        "-p",
        "--max-pages",
        type=int,
        default=10,
        help="每个组合的最大爬取页数（默认: 10）",
    )
    parser.add_argument(
        "-n",
        "--concurrency",
        type=int,
        default=None,
        help="全局并发请求数（默认由 --speed 档位决定）",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=None,
        help="请求最小延时/秒（默认由 --speed 档位决定）",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=None,
        help="请求最大延时/秒（默认由 --speed 档位决定）",
    )
    parser.add_argument(
        "--speed",
        choices=["fast", "normal", "safe"],
        default="normal",
        help="速度档位：fast=快速, normal=正常, safe=安全（默认: normal）",
    )
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="跳过详情页抓取",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="禁用断点续爬",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="清空历史断点重新开始",
    )

    # 预设模式
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速模式：3页 + 不抓详情 + speed=fast",
    )
    parser.add_argument(
        "--large",
        action="store_true",
        help="大规模模式：15页 + 抓详情 + speed=fast + 更多关键词/城市",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="增量更新模式：保留断点，只爬新数据",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出 DEBUG 级别日志",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------


async def _async_main(argv: list[str] | None = None) -> int:
    """异步主入口。"""
    args = parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    logger = logging.getLogger(__name__)

    # ---- 解析关键词和城市（支持逗号分隔） ----
    if args.keywords:
        raw_kw = " ".join(args.keywords)  # 合并回字符串供 parse_keywords_arg 处理
        keywords = parse_keywords_arg(raw_kw)
    else:
        keywords = DEFAULT_KEYWORDS[:]

    if args.cities:
        raw_ct = " ".join(args.cities)  # 同样支持逗号或空格分隔
        cities = parse_keywords_arg(raw_ct)
    else:
        cities = DEFAULT_CITIES[:]

    max_pages = args.max_pages
    concurrency = args.concurrency
    min_delay = args.delay_min
    max_delay = args.delay_max
    speed = args.speed
    fetch_detail = not args.no_detail
    resume = not args.no_resume
    clear_checkpoint = args.clear_checkpoint

    # ---- 应用预设模式 ----
    if args.quick:
        logger.info("⚡ 快速模式启用")
        max_pages = 3
        fetch_detail = False
        speed = "fast"

    if args.large:
        logger.info("大规模模式启用")
        keywords = keywords if args.keywords else LARGE_KEYWORDS[:]
        cities = cities if args.cities else LARGE_CITIES[:]
        max_pages = 15
        fetch_detail = True
        speed = "fast"

    if args.incremental:
        logger.info("增量更新模式启用")
        resume = True
        clear_checkpoint = False

    # ---- 打印任务计划 ----
    total_combos = len(keywords) * len(cities)
    estimated_jobs = total_combos * max_pages * 20  # 每页约 20 条

    logger.info("=" * 60)
    logger.info("  异步高性能爬虫 v2 - 任务计划")
    logger.info("=" * 60)
    logger.info("  关键词 (%s 个): %s", len(keywords), ", ".join(keywords))
    logger.info("  城市 (%s 个): %s", len(cities), ", ".join(cities))
    logger.info("  组合数: %s (关键词 × 城市)", total_combos)
    logger.info("  每组合最大页数: %s", max_pages)
    logger.info("  速度档位: %s", speed)
    if concurrency is not None:
        logger.info("  并发数: %s（手动指定）", concurrency)
    if min_delay is not None or max_delay is not None:
        logger.info("  延时: %s-%ss（手动指定）", min_delay, max_delay)
    logger.info("  预估职位数: ~%s 条", estimated_jobs)
    logger.info("  详情抓取: %s", "是" if fetch_detail else "否")
    logger.info("  断点续爬: %s", "是" if resume else "否")
    logger.info("  开始时间: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # ---- 确认提示 ----
    if total_combos > 10 and not (args.quick or args.large or args.incremental):
        logger.warning(
            "共 %s 个组合，预计耗时较长。"
            "使用 --quick 快速测试或 --large 开启大规模模式。",
            total_combos,
        )

    # ---- 启动爬虫 ----
    crawler = AsyncZhilianCrawler(
        keywords=keywords,
        cities=cities,
        max_pages=max_pages,
        concurrency=concurrency,
        min_delay=min_delay,
        max_delay=max_delay,
        speed=speed,
        fetch_detail=fetch_detail,
        resume=resume,
        clear_checkpoint=clear_checkpoint,
    )

    try:
        stats = await crawler.run()
    except KeyboardInterrupt:
        logger.warning("用户中断，进度已保存")
        return 130
    except Exception as exc:
        logger.exception("任务异常: %s", exc)
        return 1

    # ---- 最终报告 ----
    logger.info("=" * 60)
    logger.info("  最终统计")
    logger.info("=" * 60)
    logger.info("  入库成功: %s 条", stats.added)
    logger.info("  跳过重复: %s 条", stats.skipped)
    logger.info("  入库失败: %s 条", stats.failed_save)
    logger.info("  发现职位: %s 条", stats.jobs_found)
    logger.info("  详情请求: %s 次", stats.details_fetched)
    logger.info("  翻页数: %s 页", stats.pages_crawled)
    logger.info("  耗时: %s", stats.duration_seconds)
    logger.info("  成功率: %s%%", stats.success_rate)
    logger.info("  结束时间: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if stats.added > 0:
        logger.info("  数据存放: MySQL > job_analysis.jobs 表")
        logger.info(
            "  下一步: streamlit run web/app.py  启动可视化分析平台"
        )

    logger.info("=" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    """同步包装器，供命令行调用。"""
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
