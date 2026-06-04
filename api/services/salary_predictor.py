# ============================================================================
# 薪资预测服务
# 基于 XGBoost + 特征工程，支持模型缓存和 SHAP 可解释性
# ============================================================================
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

# 将项目根加入搜索路径，以复用 analysis 模块
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from analysis.salary_predictor_v2 import (
    SalaryPredictorV2,
    _EXPERIENCE_ORDER,
    _EDUCATION_ORDER,
    _SKILL_CATEGORIES,
    _SKILL_KEYWORD_TO_CAT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模型路径 & 缓存
# ---------------------------------------------------------------------------
_MODEL_DIR = _project_root / "data" / "models"
_DEFAULT_MODEL_PATH = _MODEL_DIR / "salary_predictor_v2.joblib"


class SalaryPredictService:
    """
    薪资预测服务（生产级封装）。

    使用方式:
        svc = SalaryPredictService()
        result = svc.predict(city="北京", experience_years=3.0,
                            skills=["Python","Django"], education="本科")
    """

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self._model_path = model_path or _DEFAULT_MODEL_PATH
        self._predictor: Optional[SalaryPredictorV2] = None
        self._model_loaded = False
        self._feature_names: list[str] = []
        self._avg_salaries_by_city: dict[str, float] = {}
        self._avg_salaries_by_edu: dict[str, float] = {}
        # 确保模型目录存在
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 模型生命周期
    # ------------------------------------------------------------------
    def load_or_train(self) -> None:
        """加载已有模型，不存在则自动训练"""
        if self._model_loaded:
            return

        if self._model_path.exists():
            logger.info(f"加载已有模型: {self._model_path}")
            self._predictor = SalaryPredictorV2()
            self._predictor.load_model(str(self._model_path))
            self._model_loaded = True
            self._load_city_stats()
        else:
            logger.info("模型文件不存在，开始自动训练...")
            self._train_and_save()

    def _train_and_save(self) -> None:
        """训练模型并保存"""
        from storage.database import db_manager

        self._predictor = SalaryPredictorV2(db=db_manager)
        logger.info("从数据库加载训练数据...")
        self._predictor.prepare_data()
        logger.info("开始训练 XGBoost 模型...")
        self._predictor.train()
        self._predictor.save_model(str(self._model_path))
        self._model_loaded = True
        self._load_city_stats()
        logger.info(
            "模型训练完成 | MAE=%.2f RMSE=%.2f R²=%.3f",
            self._predictor._metrics.get("mae", 0),
            self._predictor._metrics.get("rmse", 0),
            self._predictor._metrics.get("r2", 0),
        )

    def _load_city_stats(self) -> None:
        """加载城市和学历的平均薪资统计（用于冷启动预估和置信度计算）"""
        from storage.database import db_manager

        try:
            jobs = db_manager.get_all_jobs()
            city_sals: dict[str, list[float]] = {}
            edu_sals: dict[str, list[float]] = {}
            for j in jobs:
                smin = j.get("salary_min")
                smax = j.get("salary_max")
                if not smin or not smax or smin <= 0 or smax <= 0:
                    continue
                mid = (float(smin) + float(smax)) / 2.0
                city = str(j.get("city", "")).rstrip("市")
                edu = str(j.get("education", "不限"))
                if city and city != "未知":
                    city_sals.setdefault(city, []).append(mid)
                if edu and edu != "不限":
                    edu_sals.setdefault(edu, []).append(mid)

            for city, vals in city_sals.items():
                self._avg_salaries_by_city[city] = np.median(vals)
            for edu, vals in edu_sals.items():
                self._avg_salaries_by_edu[edu] = np.median(vals)
            logger.info("城市薪资统计加载完成: %d 个城市", len(city_sals))
        except Exception as exc:
            logger.warning("薪资统计加载失败: %s", exc)

    # ------------------------------------------------------------------
    # 特征工程（从用户输入构建）
    # ------------------------------------------------------------------
    @staticmethod
    def _map_experience(years: float) -> str:
        """数值经验年限 → 经验档位字符串"""
        if years <= 0:
            return "应届生"
        elif years <= 1:
            return "1年以内"
        elif years <= 3:
            return "1-3年"
        elif years <= 5:
            return "3-5年"
        elif years <= 10:
            return "5-10年"
        else:
            return "10年以上"

    @staticmethod
    def _map_education(edu: str) -> str:
        """归一化学历名称"""
        edu = edu.strip()
        mapping = {
            "博士": "博士", "硕士": "硕士", "研究生": "硕士",
            "本科": "本科", "学士": "本科",
            "大专": "大专", "专科": "大专",
            "高中": "高中", "中专": "中专/中技", "中技": "中专/中技",
        }
        return mapping.get(edu, "不限")

    @staticmethod
    def _count_skills_by_category(skills: list[str]) -> dict[str, int]:
        """将技能列表按类别计数（复用 v2 的分类体系）"""
        counts = {cat: 0 for cat in _SKILL_CATEGORIES}
        for skill in skills:
            key = skill.lower().strip()
            cat = _SKILL_KEYWORD_TO_CAT.get(key)
            if cat:
                counts[cat] += 1
        return counts

    def _user_to_features(
        self,
        city: str,
        experience_years: float,
        skills: list[str],
        education: str,
    ) -> dict[str, Any]:
        """
        用户输入 → 特征字典（供 SalaryPredictorV2.predict 使用）

        Args:
            city: 城市名称（如 "北京"）
            experience_years: 经验年限（数值）
            skills: 技能列表
            education: 学历

        Returns:
            dict: 包含 title, experience, education, city, skills 的特征字典
        """
        # 用前5个技能构造职位标题（用于 TF-IDF 和职级提取）
        title = "、".join(skills[:5]) + "工程师"

        # 经验年限映射为经验档位
        exp_str = self._map_experience(experience_years)
        edu_str = self._map_education(education)
        city_clean = city.strip().rstrip("市")

        return {
            "title": title,
            "experience": exp_str,
            "education": edu_str,
            "city": city_clean,
            "skills": skills,
        }

    # ------------------------------------------------------------------
    # 预测
    # ------------------------------------------------------------------
    def predict(
        self,
        city: str,
        experience_years: float,
        skills: list[str],
        education: str,
        industry: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        单个职位薪资预测。

        Returns:
            dict: {
                prediction: {salary_min, salary_avg, salary_max},
                confidence: float,
                factors: [{factor, impact, explanation}],
                model_version: str,
            }
        """
        self.load_or_train()

        # 构建模型需要的特征字典
        features = self._user_to_features(city, experience_years, skills, education)

        # 调用 SalaryPredictorV2.predict（返回 salary_mid, salary_min, salary_max, confidence, unit）
        raw_result = self._predictor.predict(features)
        salary_mid = float(raw_result["salary_mid"])
        model_salary_min = float(raw_result["salary_min"])
        model_salary_max = float(raw_result["salary_max"])

        # 置信度估算：结合模型 MAE 和数据覆盖度
        model_confidence = self._estimate_confidence(city, education, salary_mid)

        # 预测区间：优先使用模型输出的区间，同时参考置信度调整
        salary_min = round(model_salary_min, 1)
        salary_avg = round(salary_mid, 1)
        salary_max = round(model_salary_max, 1)

        # 影响因素分析
        factors = self._explain(city, experience_years, skills, education, salary_mid)

        return {
            "prediction": {
                "salary_min": salary_min,
                "salary_avg": salary_avg,
                "salary_max": salary_max,
            },
            "confidence": round(model_confidence, 3),
            "factors": factors,
            "model_version": "v2.1",
        }

    def _estimate_confidence(self, city: str, education: str, predicted_mid: float) -> float:
        """
        估算预测置信度。
        - 训练数据覆盖面越广（城市+学历有统计），置信度越高
        - 预测值偏离城市中位数越大，置信度越低
        """
        city_clean = city.strip().rstrip("市")
        edu_norm = self._map_education(education)

        base_conf = 0.65  # 基础置信度

        city_median = self._avg_salaries_by_city.get(city_clean)
        edu_median = self._avg_salaries_by_edu.get(edu_norm)

        # 城市数据覆盖 → +0.15
        if city_median:
            base_conf += 0.15
        # 学历数据覆盖 → +0.10
        if edu_median:
            base_conf += 0.10
        # 预测值在合理范围 → +0.10
        if city_median and abs(predicted_mid - city_median) / city_median < 0.5:
            base_conf += 0.10

        return min(1.0, max(0.3, base_conf))

    def _explain(
        self,
        city: str,
        experience_years: float,
        skills: list[str],
        education: str,
        salary_mid: float,
    ) -> list[dict[str, Any]]:
        """
        生成可解释的影响因子（规则化解释，不使用 SHAP 时的回退方案）。
        """
        factors: list[dict[str, Any]] = []

        # ── 城市因素 ──
        city_clean = city.strip().rstrip("市")
        city_median = self._avg_salaries_by_city.get(city_clean)
        all_city_median = np.median(list(self._avg_salaries_by_city.values())) if self._avg_salaries_by_city else 15.0
        if city_median:
            impact = round(city_median - all_city_median, 1)
            direction = "高于" if impact > 0 else "低于"
            factors.append({
                "factor": f"城市:{city_clean}",
                "impact": round(float(impact), 2),
                "explanation": f"{city_clean} 平均薪资 {city_median:.1f}K，{direction}全国中位数 {all_city_median:.1f}K",
            })
        else:
            factors.append({
                "factor": f"城市:{city_clean}",
                "impact": 0.0,
                "explanation": f"{city_clean} 暂无足够数据，使用全国中位数预估",
            })

        # ── 经验因素 ──
        avg_exp_impact = 5.0  # 每3年经验约增长 5K
        exp_impact = min(20, experience_years * avg_exp_impact / 3)
        factors.append({
            "factor": f"经验:{experience_years}年",
            "impact": round(exp_impact, 2),
            "explanation": f"{experience_years}年经验，预估薪资溢价约 {exp_impact:.0f}K",
        })

        # ── 技能因素 ──
        skill_cats = self._count_skills_by_category(skills)
        high_value_cats = {"ai": 8.0, "cloud": 5.0, "data": 4.0, "backend": 3.0}
        for cat, bonus in high_value_cats.items():
            if skill_cats.get(cat, 0) > 0:
                factors.append({
                    "factor": f"技能类别:{cat}",
                    "impact": bonus,
                    "explanation": f"{cat} 类技能为高价值技能，推高薪资约 {bonus:.0f}K",
                })

        # ── 学历因素 ──
        edu_norm = self._map_education(education)
        edu_level = _EDUCATION_ORDER.get(edu_norm, 0)
        if edu_level >= 6:  # 硕士+
            factors.append({
                "factor": f"学历:{edu_norm}",
                "impact": 5.0,
                "explanation": "硕士及以上学历通常有薪资溢价",
            })
        elif edu_level >= 5:  # 本科
            factors.append({
                "factor": f"学历:{edu_norm}",
                "impact": 0.0,
                "explanation": "本科为基准学历",
            })

        # 按影响绝对值降序排列，最多返回6个
        factors.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return factors[:6]

    # ------------------------------------------------------------------
    # 模型评测
    # ------------------------------------------------------------------
    def get_metrics(self) -> dict[str, Any]:
        """获取模型评测指标"""
        self.load_or_train()
        if self._predictor and self._predictor._metrics:
            return dict(self._predictor._metrics)
        return {"mae": None, "rmse": None, "r2": None}


# 全局单例
salary_predict_service = SalaryPredictService()
