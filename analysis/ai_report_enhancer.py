"""
AI 报告增强模块 — 接入大模型 API 生成深度分析报告。

支持的免费 API 平台（按推荐顺序）：
  1. 硅基流动 (SiliconFlow) — 聚合 DeepSeek/Qwen/Llama，注册即送额度
     https://siliconflow.cn → 获取 API Key → 填入配置
  2. DeepSeek — 中文最强，有免费额度
     https://platform.deepseek.com → 获取 API Key → 填入配置
  3. OpenAI 兼容 — 任意 OpenAI 兼容 API
  4. Google Gemini — 每日免费额度，需代理

配置方式：
  在项目根目录创建 .env 文件或设置环境变量：
    AI_API_PROVIDER=siliconflow    # 平台: siliconflow / deepseek / openai / gemini
    AI_API_KEY=sk-xxxxx            # API Key
    AI_API_MODEL=deepseek-ai/DeepSeek-V3  # 模型名（可选，有默认值）
    AI_API_BASE=https://api.siliconflow.cn/v1  # API 地址（可选，有默认值）

不配置时自动使用本地模板引擎生成报告，无需任何 API。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 默认配置 — 各平台的 API 地址和默认模型
# ---------------------------------------------------------------------------

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "name": "硅基流动",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "name": "DeepSeek",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "name": "OpenAI",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.0-flash",
        "name": "Google Gemini",
    },
}


def _load_config() -> dict[str, str]:
    """从环境变量加载 AI API 配置"""
    config = {
        "provider": os.getenv("AI_API_PROVIDER", ""),
        "api_key": os.getenv("AI_API_KEY", ""),
        "model": os.getenv("AI_API_MODEL", ""),
        "base_url": os.getenv("AI_API_BASE", ""),
    }

    # 也尝试从 .env 文件加载
    env_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, _, value = line.partition("=")
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key in config and not config[key]:
                                config[key] = value
            except Exception:
                pass

    # 填充默认值
    provider = config["provider"]
    if provider and provider in _PROVIDER_DEFAULTS:
        defaults = _PROVIDER_DEFAULTS[provider]
        if not config["model"]:
            config["model"] = defaults["model"]
        if not config["base_url"]:
            config["base_url"] = defaults["base_url"]

    return config


def is_ai_available() -> bool:
    """检查是否配置了 AI API"""
    config = _load_config()
    return bool(config["provider"] and config["api_key"])


def get_provider_name() -> str:
    """获取当前配置的 AI 平台名称"""
    config = _load_config()
    provider = config["provider"]
    if provider in _PROVIDER_DEFAULTS:
        return _PROVIDER_DEFAULTS[provider]["name"]
    return provider or "未配置"


# ---------------------------------------------------------------------------
# 报告生成 Prompt
# ---------------------------------------------------------------------------

_REPORT_SYSTEM_PROMPT = """你是一位资深招聘市场分析师。请根据提供的招聘数据统计，生成一份专业的招聘市场分析报告。

要求：
1. 使用中文撰写
2. 从数据中发现趋势、异常和洞察，不要只罗列数据
3. 给出有可操作性的建议（针对求职者、企业HR）
4. 语言专业但不枯燥，可以适当使用类比和数据可视化描述
5. 报告结构：市场概览 → 技能趋势 → 薪资洞察 → 城市机会 → 建议
6. 控制在 800-1500 字
7. 使用 Markdown 格式，包含适当的小标题和列表"""


def _build_report_prompt(stats: dict[str, Any]) -> str:
    """构建发送给 AI 的报告 prompt"""
    return f"""请根据以下招聘市场数据生成分析报告：

## 数据概览
- 总职位数: {stats.get('total_jobs', 0)}
- 有薪资数据: {stats.get('with_salary', 0)} 条
- 平均月薪: {stats.get('avg_salary', 0)} K

## 城市分布
{stats.get('city_distribution', '暂无数据')}

## 经验分布
{stats.get('exp_distribution', '暂无数据')}

## 技能 TOP 15
{stats.get('top_skills', '暂无数据')}

## 技能共现（强关联组合）
{stats.get('skill_associations', '暂无数据')}

## 薪资模型信息
- R²: {stats.get('model_r2', 'N/A')}
- MAE: {stats.get('model_mae', 'N/A')} K/月
- 关键影响因素: {stats.get('key_features', 'N/A')}

## 经验-薪资对应关系
{stats.get('exp_salary', '暂无数据')}

请开始分析："""


def _call_openai_compatible(
    messages: list[dict[str, str]],
    config: dict[str, str],
) -> str | None:
    """调用 OpenAI 兼容 API（硅基流动、DeepSeek、OpenAI 等）"""
    try:
        import urllib.request
        import urllib.error

        base_url = config["base_url"].rstrip("/")
        url = f"{base_url}/chat/completions"

        payload = json.dumps({
            "model": config["model"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['api_key']}",
            },
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"[AI报告] API调用失败: {e}")
        return None


def _call_gemini(messages: list[dict[str, str]], config: dict[str, str]) -> str | None:
    """调用 Google Gemini API"""
    try:
        import urllib.request
        import urllib.error

        base_url = config["base_url"].rstrip("/")
        model = config["model"]
        url = f"{base_url}/models/{model}:generateContent?key={config['api_key']}"

        # 转换消息格式为 Gemini 格式
        contents: list[dict] = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        payload = json.dumps({
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        print(f"[AI报告] Gemini API调用失败: {e}")
        return None


def generate_ai_report(stats: dict[str, Any]) -> str:
    """
    使用配置的 AI API 生成深度分析报告。

    Args:
        stats: 统计数据字典，由 _build_ai_report_stats 生成。

    Returns:
        Markdown 格式的分析报告文本。
    """
    config = _load_config()

    if not config["provider"] or not config["api_key"]:
        return ""

    messages = [
        {"role": "system", "content": _REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": _build_report_prompt(stats)},
    ]

    provider = config["provider"]
    if provider == "gemini":
        result = _call_gemini(messages, config)
    else:
        # siliconflow / deepseek / openai 都用 OpenAI 兼容接口
        result = _call_openai_compatible(messages, config)

    return result or ""


# ---------------------------------------------------------------------------
# 统计数据收集（供报告使用）
# ---------------------------------------------------------------------------


def collect_report_stats(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """从职位数据中收集报告所需的统计信息"""
    stats: dict[str, Any] = {}

    stats["total_jobs"] = len(jobs)
    stats["with_salary"] = sum(
        1 for j in jobs if j.get("salary_min") and j["salary_min"] > 0
    )

    # 平均薪资
    salaries = []
    for j in jobs:
        try:
            smin = float(j.get("salary_min", 0) or 0)
            smax = float(j.get("salary_max", 0) or 0)
            if smin > 0 and smax > 0:
                salaries.append((smin + smax) / 2)
        except (TypeError, ValueError):
            pass
    stats["avg_salary"] = round(sum(salaries) / len(salaries), 1) if salaries else 0

    # 城市分布
    from collections import Counter as _Counter
    city_counts = _Counter(
        str(j.get("city", "未知")) for j in jobs
    )
    top_cities = city_counts.most_common(8)
    total = max(city_counts.total(), 1)
    city_lines = []
    for city, cnt in top_cities:
        pct = cnt / total * 100
        city_lines.append(f"- {city}: {cnt} 条 ({pct:.1f}%)")
    stats["city_distribution"] = "\n".join(city_lines)

    # 经验分布
    exp_counts = _Counter(
        str(j.get("experience") or "未标注") for j in jobs
    )
    exp_lines = []
    for exp, cnt in exp_counts.most_common(8):
        exp_lines.append(f"- {exp}: {cnt} 条")
    stats["exp_distribution"] = "\n".join(exp_lines)

    # 经验-薪资关系
    exp_salary_map: dict[str, list[float]] = {}
    for j in jobs:
        exp = str(j.get("experience") or "未标注")
        try:
            smin = float(j.get("salary_min", 0) or 0)
            smax = float(j.get("salary_max", 0) or 0)
            if smin > 0 and smax > 0:
                exp_salary_map.setdefault(exp, []).append((smin + smax) / 2)
        except (TypeError, ValueError):
            pass
    exp_sal_lines = []
    for exp in ["应届生", "1年以内", "1-3年", "3-5年", "5-10年", "10年以上"]:
        vals = exp_salary_map.get(exp, [])
        if vals:
            exp_sal_lines.append(
                f"- {exp}: 平均 {sum(vals)/len(vals):.1f}K/月 ({len(vals)} 条)"
            )
    stats["exp_salary"] = "\n".join(exp_sal_lines) if exp_sal_lines else "暂无数据"

    return stats


def collect_skill_stats(stats: dict[str, Any]) -> None:
    """补充技能相关的统计信息"""
    try:
        from analysis.skill_nlp import skill_analyzer

        freq = skill_analyzer.get_skills_frequency(top_n=15)
        if freq:
            skill_lines = []
            for rank, (skill, count) in enumerate(freq.most_common(15), 1):
                skill_lines.append(f"{rank}. {skill} ({count} 次)")
            stats["top_skills"] = "\n".join(skill_lines)

        pairs = skill_analyzer.get_skill_associations(
            min_support=0.01, min_confidence=0.3
        )
        if pairs:
            pair_lines = []
            for p in pairs[:8]:
                pair_lines.append(
                    f"- {p['antecedent']} + {p['consequent']} → "
                    f"支持度 {p['support']:.1%}, 置信度 {p['confidence']:.1%}"
                )
            stats["skill_associations"] = "\n".join(pair_lines)
    except Exception:
        pass


def chat_with_ai(
    messages: list[dict[str, str]],
    provider: str,
    api_key: str,
    model: str = "",
    base_url: str = "",
) -> str | None:
    """
    通用 AI 对话接口 — 支持运行时传入配置，不依赖环境变量。

    Args:
        messages: 对话消息列表 [{"role": "user/system/assistant", "content": "..."}]
        provider: 平台 (siliconflow / deepseek / openai / gemini)
        api_key: API Key
        model: 模型名（可选，默认使用各平台推荐模型）
        base_url: API 地址（可选，默认使用各平台官方地址）

    Returns:
        AI 回复文本，失败返回 None
    """
    # 构建运行时配置
    defaults = _PROVIDER_DEFAULTS.get(provider, {})
    config = {
        "provider": provider,
        "api_key": api_key,
        "model": model or defaults.get("model", ""),
        "base_url": base_url or defaults.get("base_url", ""),
    }

    if not config["model"] or not config["base_url"]:
        return None

    if provider == "gemini":
        return _call_gemini(messages, config)
    else:
        return _call_openai_compatible(messages, config)


def collect_model_stats(stats: dict[str, Any]) -> None:
    """补充薪资模型相关的统计信息"""
    try:
        from analysis.salary_predictor_v2 import salary_predictor_v2

        if salary_predictor_v2.is_trained:
            m = salary_predictor_v2.metrics
            if m:
                stats["model_r2"] = f"{m.get('r2', 0):.4f}"
                stats["model_mae"] = f"{m.get('mae', 0):.2f}"
                stats["model_rmse"] = f"{m.get('rmse', 0):.2f}"

            try:
                imp = salary_predictor_v2.get_feature_importance(top_n=5)
                if imp:
                    feat_lines = []
                    for fi in imp:
                        name = fi['feature'].replace('tfidf_', '').replace('skill_', '')
                        feat_lines.append(f"- {name}: 权重 {fi['importance']:.4f}")
                    stats["key_features"] = "\n".join(feat_lines)
            except Exception:
                pass
    except Exception:
        pass
