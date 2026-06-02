"""
薪资预测模块。

基于历史招聘数据训练回归模型，根据城市、行业、经验、学历、技能等特征
预测职位月薪区间（单位：K/月），支持模型持久化与特征重要性分析。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from analysis.data_cleaner import (
    CITY_MAPPING,
    EDUCATION_MAPPING,
    EXPERIENCE_MAPPING,
    SKILL_MAPPING,
)
from config.settings import BASE_DIR
from storage.database import DatabaseManager, db_manager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 默认模型保存路径
_DEFAULT_MODEL_PATH: Path = BASE_DIR / "data" / "models" / "salary_predictor.joblib"

# 经验档位 → 有序数值（越大表示经验越丰富）
_EXPERIENCE_ORDER: dict[str, int] = {
    "不限": 0,
    "应届生": 0,
    "1年以内": 1,
    "1-3年": 2,
    "3-5年": 3,
    "5-10年": 4,
    "10年以上": 5,
}

# 学历档位 → 有序数值（越大表示学历越高）
_EDUCATION_ORDER: dict[str, int] = {
    "不限": 0,
    "初中及以下": 1,
    "高中": 2,
    "中专/中技": 3,
    "大专": 4,
    "本科": 5,
    "硕士": 6,
    "博士": 7,
}

# 判定为 AI 相关技能的关键词（小写匹配）
_AI_SKILL_KEYWORDS: frozenset[str] = frozenset(
    {
        "机器学习",
        "深度学习",
        "nlp",
        "计算机视觉",
        "pytorch",
        "tensorflow",
        "keras",
        "llm",
        "大模型",
        "神经网络",
        "人工智能",
        "ai",
        "gpt",
        "transformer",
        "bert",
        "opencv",
        "强化学习",
        "自然语言处理",
        "生成式",
    }
)

# 特征列定义
_NUMERIC_FEATURES = ["experience_level", "education_level", "skill_count", "has_ai_skill"]
_CATEGORICAL_FEATURES = ["city", "industry"]
_ALL_FEATURES = _CATEGORICAL_FEATURES + _NUMERIC_FEATURES

# 训练所需最少样本量
_MIN_SAMPLES = 10


# ---------------------------------------------------------------------------
# 薪资预测器
# ---------------------------------------------------------------------------


class SalaryPredictor:
    """
    职位薪资回归预测器。

    使用随机森林对薪资中位数（(salary_min + salary_max) / 2）进行建模，
    特征包括城市、行业、经验、学历、技能数量及是否含 AI 技能等。
    """

    def __init__(self, db: DatabaseManager) -> None:
        """
        Args:
            db: 数据库管理器实例，用于读取训练数据。
        """
        self._db = db
        self._pipeline: Pipeline | None = None
        self._metrics: dict[str, float] | None = None
        self._model_type: str | None = None
        self._X: pd.DataFrame | None = None
        self._y: pd.Series | None = None
        self._model_path: Path = _DEFAULT_MODEL_PATH

    # ------------------------------------------------------------------
    # 特征工程
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_city(city: str | None) -> str:
        """标准化城市名称。"""
        if not city or not str(city).strip():
            return "未知"
        raw = str(city).strip().replace("市", "")
        if "·" in raw:
            raw = raw.split("·", 1)[0].strip()
        return CITY_MAPPING.get(raw, CITY_MAPPING.get(raw + "市", raw))

    @staticmethod
    def _normalize_experience(experience: str | None) -> str:
        """标准化工作经验档位。"""
        if not experience or not str(experience).strip():
            return "不限"
        text = str(experience).strip()
        if text in EXPERIENCE_MAPPING:
            return EXPERIENCE_MAPPING[text]
        compact = text.replace(" ", "")
        for key, value in EXPERIENCE_MAPPING.items():
            if key.replace(" ", "") == compact:
                return value
        return text

    @staticmethod
    def _normalize_education(education: str | None) -> str:
        """标准化学历档位。"""
        if not education or not str(education).strip():
            return "不限"
        text = str(education).strip()
        if text in EDUCATION_MAPPING:
            return EDUCATION_MAPPING[text]
        for key, value in EDUCATION_MAPPING.items():
            if key in text:
                return value
        return text

    @staticmethod
    def _count_skills(skills: Any) -> int:
        """统计技能数量。"""
        if skills is None:
            return 0
        if isinstance(skills, list):
            return len([s for s in skills if s])
        if isinstance(skills, str) and skills.strip():
            parts = re.split(r"[,，、;；|/]", skills)
            return len([p for p in parts if p.strip()])
        return 0

    @classmethod
    def _has_ai_skill(cls, job: dict[str, Any]) -> int:
        """
        判断职位是否包含 AI 相关技能。

        检查 ``skills`` 列表及 ``title`` / ``description`` 文本中的关键词。

        Returns:
            ``1`` 表示包含 AI 技能，``0`` 表示不包含。
        """
        tokens: list[str] = []

        raw_skills = job.get("skills")
        if isinstance(raw_skills, list):
            tokens.extend(str(s).lower() for s in raw_skills if s)
        elif isinstance(raw_skills, str):
            tokens.extend(raw_skills.lower().split())

        for skill in SKILL_MAPPING.values():
            if skill.lower() in _AI_SKILL_KEYWORDS:
                pass  # 仅用于词典参考

        title = str(job.get("title") or "").lower()
        description = str(job.get("description") or "").lower()
        combined_text = " ".join(tokens) + " " + title + " " + description

        for keyword in _AI_SKILL_KEYWORDS:
            if keyword in combined_text:
                return 1

        for token in tokens:
            mapped = SKILL_MAPPING.get(token, token)
            if mapped.lower() in _AI_SKILL_KEYWORDS or token in _AI_SKILL_KEYWORDS:
                return 1
            for keyword in _AI_SKILL_KEYWORDS:
                if keyword in token or keyword in mapped.lower():
                    return 1

        return 0

    def _job_to_features(self, job: dict[str, Any]) -> dict[str, Any] | None:
        """
        将单条职位记录转换为特征字典。

        Args:
            job: 职位字典。

        Returns:
            特征字典；薪资缺失时返回 ``None``。
        """
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")

        try:
            smin = float(salary_min) if salary_min is not None else None
            smax = float(salary_max) if salary_max is not None else None
        except (TypeError, ValueError):
            return None

        if smin is None or smax is None or smin <= 0 or smax <= 0:
            return None
        if smin > smax:
            smin, smax = smax, smin

        experience = self._normalize_experience(job.get("experience"))
        education = self._normalize_education(job.get("education"))

        return {
            "city": self._normalize_city(job.get("city")),
            "industry": (str(job.get("industry")).strip() if job.get("industry") else "未知"),
            "experience_level": _EXPERIENCE_ORDER.get(experience, 0),
            "education_level": _EDUCATION_ORDER.get(education, 0),
            "skill_count": self._count_skills(job.get("skills")),
            "has_ai_skill": self._has_ai_skill(job),
            "salary_mid": (smin + smax) / 2.0,
        }

    def _features_dict_to_row(self, features_dict: dict[str, Any]) -> dict[str, Any]:
        """
        将预测入参字典转换为与训练一致的特征行。

        Args:
            features_dict: 含 city / industry / experience / education / skills 等键。

        Returns:
            模型输入特征行（不含目标列）。
        """
        experience = self._normalize_experience(features_dict.get("experience"))
        education = self._normalize_education(features_dict.get("education"))

        skill_count = features_dict.get("skill_count")
        if skill_count is None:
            skill_count = self._count_skills(features_dict.get("skills"))

        has_ai = features_dict.get("has_ai_skill")
        if has_ai is None:
            has_ai = self._has_ai_skill(features_dict)

        return {
            "city": self._normalize_city(features_dict.get("city")),
            "industry": (
                str(features_dict.get("industry")).strip()
                if features_dict.get("industry")
                else "未知"
            ),
            "experience_level": _EXPERIENCE_ORDER.get(experience, 0),
            "education_level": _EDUCATION_ORDER.get(education, 0),
            "skill_count": int(skill_count),
            "has_ai_skill": int(has_ai),
        }

    def prepare_data(self) -> tuple[pd.DataFrame, pd.Series]:
        """
        从数据库加载职位数据并完成特征工程。

        Returns:
            ``(X, y)``：特征 DataFrame 与目标 Series（薪资中位数，K/月）。

        Raises:
            ValueError: 有效样本数不足 ``_MIN_SAMPLES``。
        """
        jobs = self._db.get_all_jobs()
        rows: list[dict[str, Any]] = []

        for job in jobs:
            features = self._job_to_features(job)
            if features is not None:
                rows.append(features)

        if len(rows) < _MIN_SAMPLES:
            raise ValueError(
                f"有效训练样本不足 {_MIN_SAMPLES} 条（当前 {len(rows)} 条），"
                "请先录入含薪资的记录后再训练。"
            )

        df = pd.DataFrame(rows)
        y = df["salary_mid"].astype(float)
        X = df[_ALL_FEATURES].copy()

        self._X = X
        self._y = y
        return X, y

    @staticmethod
    def _build_pipeline(model_type: str) -> Pipeline:
        """
        构建预处理 + 回归器 Pipeline。

        Args:
            model_type: 模型类型，当前仅支持 ``random_forest``。

        Raises:
            ValueError: 不支持的模型类型。
        """
        if model_type != "random_forest":
            raise ValueError(
                f"不支持的模型类型: {model_type!r}，当前仅支持 'random_forest'"
            )

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    _CATEGORICAL_FEATURES,
                ),
                ("num", "passthrough", _NUMERIC_FEATURES),
            ],
            remainder="drop",
        )

        regressor = RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )

        return Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", regressor),
            ]
        )

    def train(
        self,
        model_type: str = "random_forest",
        test_size: float = 0.2,
        save: bool = True,
    ) -> dict[str, float]:
        """
        训练薪资预测模型并评估。

        Args:
            model_type: 模型类型，默认 ``random_forest``。
            test_size: 测试集比例，默认 20%。
            save: 训练完成后是否自动保存模型，默认 ``True``。

        Returns:
            评估指标字典，包含 ``r2``、``mae``、``rmse``、``train_size``、``test_size``。

        Raises:
            ValueError: 样本不足或模型类型不支持。
        """
        X, y = self.prepare_data()

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=42,
        )

        pipeline = self._build_pipeline(model_type)
        pipeline.fit(X_train, y_train)

        y_pred = pipeline.predict(X_test)
        metrics = {
            "r2": float(r2_score(y_test, y_pred)),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "train_size": float(len(X_train)),
            "test_size": float(len(X_test)),
        }

        self._pipeline = pipeline
        self._metrics = metrics
        self._model_type = model_type

        if save:
            self.save_model()

        return metrics

    def predict(self, features_dict: dict[str, Any]) -> dict[str, Any]:
        """
        对新职位预测薪资（K/月）。

        Args:
            features_dict: 特征字典，需包含 ``city``，可选 ``industry``、
                ``experience``、``education``、``skills`` / ``skill_count``、
                ``has_ai_skill`` 等。

        Returns:
            预测结果，含 ``salary_mid``、``salary_min``、``salary_max``、``unit``。

        Raises:
            RuntimeError: 模型尚未训练或加载。
        """
        if self._pipeline is None:
            raise RuntimeError("模型未训练或未加载，请先调用 train() 或 load_model()")

        row = self._features_dict_to_row(features_dict)
        X = pd.DataFrame([row], columns=_ALL_FEATURES)
        salary_mid = float(self._pipeline.predict(X)[0])
        salary_mid = max(0.0, round(salary_mid, 2))

        # 以中位数为中心给出约 ±10% 的参考区间
        spread = max(1.0, salary_mid * 0.1)
        return {
            "salary_mid": salary_mid,
            "salary_min": round(max(0.0, salary_mid - spread), 2),
            "salary_max": round(salary_mid + spread, 2),
            "unit": "K/月",
        }

    def get_feature_importance(self, top_n: int = 20) -> list[dict[str, Any]]:
        """
        返回训练后模型的特征重要性排序。

        Args:
            top_n: 返回前 N 个重要特征；``<=0`` 表示返回全部。

        Returns:
            列表项为 ``{"feature": 名称, "importance": 权重}``，按重要性降序。

        Raises:
            RuntimeError: 模型尚未训练或加载。
        """
        if self._pipeline is None:
            raise RuntimeError("模型未训练或未加载，请先调用 train() 或 load_model()")

        regressor: RandomForestRegressor = self._pipeline.named_steps["regressor"]
        preprocessor: ColumnTransformer = self._pipeline.named_steps["preprocessor"]

        try:
            feature_names = preprocessor.get_feature_names_out()
        except AttributeError:
            feature_names = [f"feature_{i}" for i in range(len(regressor.feature_importances_))]

        importances = regressor.feature_importances_
        pairs = sorted(
            zip(feature_names, importances),
            key=lambda item: item[1],
            reverse=True,
        )

        result = [
            {"feature": name, "importance": round(float(score), 6)}
            for name, score in pairs
        ]

        if top_n > 0:
            return result[:top_n]
        return result

    # ------------------------------------------------------------------
    # 模型持久化
    # ------------------------------------------------------------------

    def save_model(self, path: str | Path | None = None) -> Path:
        """
        使用 joblib 将模型 Pipeline 及元数据保存到磁盘。

        Args:
            path: 保存路径，默认 ``data/models/salary_predictor.joblib``。

        Returns:
            实际写入的文件路径。

        Raises:
            RuntimeError: 当前无已训练模型。
        """
        if self._pipeline is None:
            raise RuntimeError("无可用模型可保存，请先调用 train()")

        save_path = Path(path) if path else self._model_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "pipeline": self._pipeline,
            "metrics": self._metrics,
            "model_type": self._model_type,
            "feature_columns": _ALL_FEATURES,
        }
        joblib.dump(payload, save_path)
        self._model_path = save_path
        return save_path

    def load_model(self, path: str | Path | None = None) -> dict[str, Any]:
        """
        从磁盘加载已保存的模型。

        Args:
            path: 模型文件路径，默认使用上次保存路径。

        Returns:
            加载的元数据字典（含 ``metrics``、``model_type`` 等）。

        Raises:
            FileNotFoundError: 模型文件不存在。
        """
        load_path = Path(path) if path else self._model_path
        if not load_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {load_path}")

        payload = joblib.load(load_path)
        self._pipeline = payload["pipeline"]
        self._metrics = payload.get("metrics")
        self._model_type = payload.get("model_type")
        self._model_path = load_path
        return payload

    @property
    def is_trained(self) -> bool:
        """模型是否已训练或已加载。"""
        return self._pipeline is not None

    @property
    def metrics(self) -> dict[str, float] | None:
        """最近一次训练的评估指标。"""
        return self._metrics


# 全局实例：项目内统一引用
salary_predictor = SalaryPredictor(db_manager)
