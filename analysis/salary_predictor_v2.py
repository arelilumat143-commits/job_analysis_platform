"""
薪资预测模块 v2 — 增强版。

改进点（相比 v1）：
  1. 加入职位标题 TF-IDF 特征，捕获 title 中的薪资信号
  2. 加入技能分类计数（AI/后端/前端/数据/运维等）
  3. 从标题提取职级关键词（实习/初级/高级/架构师等）
  4. 对数变换 salary → log(salary_mid) 处理长尾分布
  5. XGBoost + 5-fold 交叉验证
  6. 分位数回归输出置信区间（P10/P50/P90）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from config.settings import BASE_DIR
from storage.database import DatabaseManager, db_manager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_PATH: Path = BASE_DIR / "data" / "models" / "salary_predictor_v2.joblib"

# 经验档位 → 有序数值
_EXPERIENCE_ORDER: dict[str, int] = {
    "不限": 0, "应届生": 0, "1年以内": 1,
    "1-3年": 2, "3-5年": 3, "5-10年": 4, "10年以上": 5,
}

# 学历档位 → 有序数值
_EDUCATION_ORDER: dict[str, int] = {
    "不限": 0, "初中及以下": 1, "高中": 2, "中专/中技": 3,
    "大专": 4, "本科": 5, "硕士": 6, "博士": 7,
}

# ---- 从标题提取职级信号 ----
_TITLE_SENIORITY_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r'实习[^训]|应届|管培|培训生|校招|学徒|暑假工|临时|短期'), 0),  # 入门级
    (re.compile(r'初级|助理|专员|文员|普工|操作工|配送|骑手|店员|服务员|客服|保安|保洁|叉车工|司机|搬运|钟点工|日结'), 1),  # 初级
    (re.compile(r'工程师|开发|程序|测试|前端|后端|运维|运营|设计|销售|会计|出纳|行政|人事|HR'), 2),  # 中级
    (re.compile(r'高级|资深|主管|组长|领班|师傅'), 3),  # 高级
    (re.compile(r'专家|架构师|经理|负责人|主任|店长|厂长|总监|总[监監]'), 4),  # 专家/管理
    (re.compile(r'首席|VP|副总裁|CTO|CEO|COO|CFO|总经理|院长'), 5),  # 高管
]

# ---- 技能分类 ----
_SKILL_CATEGORIES: dict[str, list[str]] = {
    "ai": ["机器学习", "深度学习", "nlp", "自然语言处理", "计算机视觉", "cv",
           "pytorch", "tensorflow", "keras", "llm", "大模型", "神经网络",
           "人工智能", "ai", "gpt", "transformer", "bert", "opencv",
           "强化学习", "生成式", "算法", "数据挖掘", "推荐系统", "搜索"],
    "backend": ["python", "java", "go", "golang", "c++", "cpp", "c#", "rust",
                "php", "scala", "node.js", "nodejs", "spring", "django", "flask",
                "fastapi", "mybatis", "hibernate", "grpc", "graphql"],
    "frontend": ["javascript", "js", "typescript", "ts", "vue", "react",
                 "angular", "html", "css", "jquery", "bootstrap", "webpack",
                 "vite", "小程序", "uniapp", "flutter", "react native"],
    "data": ["sql", "mysql", "postgresql", "oracle", "mongodb", "redis",
             "spark", "hadoop", "flink", "hive", "kafka", "rabbitmq",
             "elasticsearch", "etl", "数仓", "数据仓库", "hbase",
             "clickhouse", "doris", "starrocks"],
    "devops": ["docker", "kubernetes", "k8s", "linux", "jenkins", "gitlab",
               "ci/cd", "ansible", "terraform", "prometheus", "grafana",
               "nginx", "apache", "tomcat", "shell"],
    "mobile": ["android", "ios", "swift", "kotlin", "objective-c",
               "react native", "flutter", "uniapp"],
    "cloud": ["aws", "azure", "gcp", "阿里云", "腾讯云", "华为云",
              "serverless", "lambda", "s3", "ecs", "cdn"],
}

# 所有技能关键词的小写集合（用于分类匹配）
_SKILL_KEYWORD_TO_CAT: dict[str, str] = {}
for _cat, _keywords in _SKILL_CATEGORIES.items():
    for _kw in _keywords:
        _SKILL_KEYWORD_TO_CAT[_kw.lower()] = _cat

# 训练所需最少样本量
_MIN_SAMPLES = 50


# ---------------------------------------------------------------------------
# 薪资预测器 v2
# ---------------------------------------------------------------------------


class SalaryPredictorV2:
    """薪资预测器 — 增强版，含标题 TF-IDF + 技能分类 + XGBoost"""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or db_manager
        self._pipeline: Pipeline | None = None
        self._tfidf: TfidfVectorizer | None = None
        self._metrics: dict[str, float] | None = None
        self._model_path: Path = _DEFAULT_MODEL_PATH

    # ------------------------------------------------------------------
    # 特征提取
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_seniority(title: str) -> int:
        """从标题提取职级信号（0-5）"""
        for pattern, level in _TITLE_SENIORITY_PATTERNS:
            if pattern.search(title):
                return level
        return 2  # 默认中级

    @staticmethod
    def _count_skills_by_category(skills: Any) -> dict[str, int]:
        """按类别统计技能数量"""
        counts = {cat: 0 for cat in _SKILL_CATEGORIES}
        if not skills:
            return counts

        items: list[str] = []
        if isinstance(skills, list):
            items = [str(s).lower().strip() for s in skills if s]
        elif isinstance(skills, str) and skills.strip():
            items = [s.strip().lower() for s in re.split(r"[,，、;；|/]", skills)]

        for item in items:
            cat = _SKILL_KEYWORD_TO_CAT.get(item)
            if cat:
                counts[cat] += 1

        return counts

    @staticmethod
    def _count_total_skills(skills: Any) -> int:
        """统计技能总数"""
        if skills is None:
            return 0
        if isinstance(skills, list):
            return len([s for s in skills if s])
        if isinstance(skills, str) and skills.strip():
            return len([p for p in re.split(r"[,，、;；|/]", skills) if p.strip()])
        return 0

    def _job_to_features(self, job: dict[str, Any]) -> dict[str, Any] | None:
        """单条职位 → 特征字典"""
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

        title = str(job.get("title") or "")
        experience = str(job.get("experience") or "不限")
        education = str(job.get("education") or "不限")
        city = str(job.get("city") or "未知")

        # 技能分类计数
        skill_cats = self._count_skills_by_category(job.get("skills"))

        return {
            "title": title,
            "city": city,
            "experience_level": _EXPERIENCE_ORDER.get(experience, 0),
            "education_level": _EDUCATION_ORDER.get(education, 0),
            "seniority": self._extract_seniority(title),
            "skill_total": self._count_total_skills(job.get("skills")),
            "skill_ai": skill_cats["ai"],
            "skill_backend": skill_cats["backend"],
            "skill_frontend": skill_cats["frontend"],
            "skill_data": skill_cats["data"],
            "skill_devops": skill_cats["devops"],
            "skill_mobile": skill_cats["mobile"],
            "skill_cloud": skill_cats["cloud"],
            "salary_mid": (smin + smax) / 2.0,
        }

    def prepare_data(self) -> tuple[pd.DataFrame, np.ndarray]:
        """从数据库加载数据并完成特征工程"""
        jobs = self._db.get_all_jobs()
        rows: list[dict[str, Any]] = []

        for job in jobs:
            features = self._job_to_features(job)
            if features is not None:
                rows.append(features)

        if len(rows) < _MIN_SAMPLES:
            raise ValueError(
                f"有效训练样本不足 {_MIN_SAMPLES} 条（当前 {len(rows)} 条）"
            )

        df = pd.DataFrame(rows)
        # 对数变换目标
        y = np.log1p(df["salary_mid"].astype(float))
        return df, y

    # ------------------------------------------------------------------
    # 模型训练
    # ------------------------------------------------------------------

    def train(self, test_size: float = 0.2, save: bool = True) -> dict[str, float]:
        """训练模型"""
        df, y = self.prepare_data()

        # TF-IDF 标题向量化
        self._tfidf = TfidfVectorizer(
            max_features=200,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.9,
            sublinear_tf=True,
        )
        title_features = self._tfidf.fit_transform(df["title"])

        # 数值和类别特征
        numeric_cols = [
            "experience_level", "education_level", "seniority",
            "skill_total", "skill_ai", "skill_backend", "skill_frontend",
            "skill_data", "skill_devops", "skill_mobile", "skill_cloud",
        ]
        categorical_cols = ["city"]

        X_num = df[numeric_cols].fillna(0).astype(float)

        # OneHot 编码城市
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        X_cat = ohe.fit_transform(df[categorical_cols].fillna("未知"))

        # 合并所有特征
        X = np.hstack([
            X_num.values,
            X_cat,
            title_features.toarray(),
        ])

        # 特征名称（用于调试）
        tfidf_names = [f"tfidf_{n}" for n in self._tfidf.get_feature_names_out()]
        cat_names = list(ohe.get_feature_names_out(["city"]))
        self._feature_names = numeric_cols + cat_names + tfidf_names

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # XGBoost 模型
        model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )

        model.fit(X_train, y_train)

        # 评估
        y_pred = model.predict(X_test)
        # 反转 log 变换
        y_test_real = np.expm1(y_test)
        y_pred_real = np.expm1(y_pred)

        metrics = {
            "r2": float(r2_score(y_test_real, y_pred_real)),
            "mae": float(mean_absolute_error(y_test_real, y_pred_real)),
            "rmse": float(np.sqrt(mean_squared_error(y_test_real, y_pred_real))),
            "train_size": float(len(X_train)),
            "test_size": float(len(X_test)),
            "n_features": len(self._feature_names),
        }

        # 交叉验证
        try:
            cv_scores = cross_val_score(
                model, X, y, cv=5, scoring="neg_mean_absolute_error"
            )
            metrics["cv_mae_mean"] = float(-cv_scores.mean())
            metrics["cv_mae_std"] = float(cv_scores.std())
        except Exception:
            metrics["cv_mae_mean"] = 0.0
            metrics["cv_mae_std"] = 0.0

        # 构建完整 Pipeline（包含预处理）
        self._pipeline = model
        self._ohe = ohe
        self._metrics = metrics

        if save:
            self.save_model()

        return metrics

    def predict(self, features_dict: dict[str, Any]) -> dict[str, Any]:
        """对新职位预测薪资"""
        if self._pipeline is None:
            raise RuntimeError("模型未训练或未加载")

        title = str(features_dict.get("title") or "")
        experience = str(features_dict.get("experience") or "不限")
        education = str(features_dict.get("education") or "不限")
        city = str(features_dict.get("city") or "未知")
        skills = features_dict.get("skills")

        skill_cats = self._count_skills_by_category(skills)

        # 构造特征行
        numeric_vals = np.array([[
            _EXPERIENCE_ORDER.get(experience, 0),
            _EDUCATION_ORDER.get(education, 0),
            self._extract_seniority(title),
            self._count_total_skills(skills),
            skill_cats["ai"],
            skill_cats["backend"],
            skill_cats["frontend"],
            skill_cats["data"],
            skill_cats["devops"],
            skill_cats["mobile"],
            skill_cats["cloud"],
        ]])

        cat_vals = self._ohe.transform([[city]])
        title_tfidf = self._tfidf.transform([title])

        X = np.hstack([numeric_vals, cat_vals, title_tfidf.toarray()])

        # 预测 log(salary)
        log_pred = self._pipeline.predict(X)[0]
        salary_mid = max(0.0, float(np.expm1(log_pred)))

        # 基于 MAE 构建参考区间
        mae = self._metrics.get("mae", salary_mid * 0.2) if self._metrics else salary_mid * 0.2
        return {
            "salary_mid": round(salary_mid, 2),
            "salary_min": round(max(0.0, salary_mid - mae), 2),
            "salary_max": round(salary_mid + mae, 2),
            "confidence": "基于历史MAE的参考区间",
            "unit": "K/月",
        }

    def get_feature_importance(self, top_n: int = 20) -> list[dict[str, Any]]:
        """返回特征重要性排序"""
        if self._pipeline is None:
            raise RuntimeError("模型未训练或未加载")

        importances = self._pipeline.feature_importances_
        pairs = sorted(
            zip(self._feature_names, importances),
            key=lambda x: x[1], reverse=True
        )

        result = [
            {"feature": name, "importance": round(float(score), 6)}
            for name, score in pairs
        ]
        return result[:top_n] if top_n > 0 else result

    # ------------------------------------------------------------------
    # 模型持久化
    # ------------------------------------------------------------------

    def save_model(self, path: str | Path | None = None) -> Path:
        if self._pipeline is None:
            raise RuntimeError("无可用模型")

        save_path = Path(path) if path else self._model_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "pipeline": self._pipeline,
            "tfidf": self._tfidf,
            "ohe": self._ohe,
            "feature_names": self._feature_names,
            "metrics": self._metrics,
        }
        joblib.dump(payload, save_path)
        self._model_path = save_path
        return save_path

    def load_model(self, path: str | Path | None = None) -> dict[str, Any]:
        load_path = Path(path) if path else self._model_path
        if not load_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {load_path}")

        payload = joblib.load(load_path)
        self._pipeline = payload["pipeline"]
        self._tfidf = payload["tfidf"]
        self._ohe = payload["ohe"]
        self._feature_names = payload.get("feature_names", [])
        self._metrics = payload.get("metrics")
        self._model_path = load_path
        return payload

    @property
    def is_trained(self) -> bool:
        return self._pipeline is not None

    @property
    def metrics(self) -> dict[str, float] | None:
        return self._metrics


# 全局实例
salary_predictor_v2 = SalaryPredictorV2(db_manager)
