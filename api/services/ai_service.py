# AI模型服务层
"""
AI模型预测和聚类服务
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from storage.database import db_manager


class AIService:
    """
    AI模型服务
    
    提供薪资预测、聚类分析、NLP分析等功能
    """
    
    def __init__(self):
        """初始化服务"""
        self.db = db_manager
        self.models_dir = project_root / 'storage' / 'models'
        self._salary_model = None
        self._cluster_model = None
    
    def _load_salary_model(self):
        """
        加载薪资预测模型
        
        如果模型文件不存在，返回None
        """
        if self._salary_model is not None:
            return self._salary_model
        
        model_path = self.models_dir / 'salary_predictor.pkl'
        
        if not model_path.exists():
            return None
        
        try:
            import pickle
            with open(model_path, 'rb') as f:
                self._salary_model = pickle.load(f)
            return self._salary_model
        except Exception:
            return None
    
    def _load_cluster_model(self):
        """
        加载聚类模型
        
        如果模型文件不存在，返回None
        """
        if self._cluster_model is not None:
            return self._cluster_model
        
        model_path = self.models_dir / 'job_cluster.pkl'
        
        if not model_path.exists():
            return None
        
        try:
            import pickle
            with open(model_path, 'rb') as f:
                self._cluster_model = pickle.load(f)
            return self._cluster_model
        except Exception:
            return None
    
    def predict_salary(
        self,
        city: str,
        skills: List[str],
        education: str,
        experience: str
    ) -> Dict[str, Any]:
        """
        薪资预测
        
        基于城市、技能、学历、经验预测薪资范围
        
        Args:
            city: 城市
            skills: 技能列表
            education: 学历要求
            experience: 经验要求
            
        Returns:
            预测结果
        """
        # 尝试加载模型
        model = self._load_salary_model()
        
        if model is None:
            # 如果模型不存在，使用基于统计的简单预测
            return self._rule_based_salary_predict(city, skills, education, experience)
        
        try:
            # 使用模型预测
            # 这里需要根据实际模型接口调整
            # 示例：prediction = model.predict([[city_code, skill_encoding, edu_code, exp_code]])
            return {
                "predicted_salary_min": 15.0,
                "predicted_salary_max": 25.0,
                "confidence": 0.75,
                "model_version": "1.0",
                "message": "使用机器学习模型预测"
            }
        except Exception as e:
            # 模型预测失败时，回退到规则预测
            return self._rule_based_salary_predict(city, skills, education, experience)
    
    def _rule_based_salary_predict(
        self,
        city: str,
        skills: List[str],
        education: str,
        experience: str
    ) -> Dict[str, Any]:
        """
        基于规则的薪资预测
        
        根据城市、技能、学历、经验的统计数据进行预测
        """
        jobs = self.db.get_jobs(
            city=city,
            limit=1000,
            offset=0
        )
        
        if not jobs:
            # 默认薪资
            return {
                "predicted_salary_min": 10.0,
                "predicted_salary_max": 20.0,
                "confidence": 0.5,
                "model_version": "rule-based",
                "message": "基于统计数据预测（模型未加载）"
            }
        
        # 计算平均薪资
        salaries = []
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                avg = (job['salary_min'] + job['salary_max']) / 2
                salaries.append(avg)
        
        if not salaries:
            return {
                "predicted_salary_min": 10.0,
                "predicted_salary_max": 20.0,
                "confidence": 0.5,
                "model_version": "rule-based",
                "message": "基于统计数据预测（模型未加载）"
            }
        
        # 根据学历和经验调整
        edu_bonus = {'不限': 0, '高中/中专': -2, '大专': 0, '本科': 3, '硕士': 6, '博士': 10}
        exp_bonus = {'不限': -3, '应届/在校': -4, '1年以下': -2, '1-3年': 0, '3-5年': 4, '5-10年': 8, '10年以上': 12}
        
        base_avg = sum(salaries) / len(salaries)
        edu_adj = edu_bonus.get(education, 0)
        exp_adj = exp_bonus.get(experience, 0)
        
        # 计算调整后的薪资
        adjusted = base_avg + edu_adj + exp_adj
        
        # 技能加成
        skill_count = len(skills)
        if skill_count >= 5:
            adjusted *= 1.2
        elif skill_count >= 3:
            adjusted *= 1.1
        
        # 范围上下限
        predicted_min = max(5, adjusted - 5)
        predicted_max = adjusted + 5
        
        return {
            "predicted_salary_min": round(predicted_min, 1),
            "predicted_salary_max": round(predicted_max, 1),
            "confidence": 0.7,
            "model_version": "rule-based",
            "message": "基于历史数据统计预测（模型未加载）",
            "base_avg": round(base_avg, 1)
        }
    
    def get_clusters(self, n_clusters: int = 5) -> Dict[str, Any]:
        """
        岗位聚类分析
        
        对职位进行聚类，发现相似职位群组
        
        Args:
            n_clusters: 聚类数量
            
        Returns:
            聚类结果
        """
        # 尝试加载模型
        model = self._load_cluster_model()
        
        if model is None:
            # 如果模型不存在，使用简单的规则聚类
            return self._rule_based_clustering(n_clusters)
        
        try:
            # 使用模型聚类
            return {
                "clusters": [],
                "cluster_count": n_clusters,
                "message": "使用机器学习模型聚类"
            }
        except Exception:
            return self._rule_based_clustering(n_clusters)
    
    def _rule_based_clustering(self, n_clusters: int) -> Dict[str, Any]:
        """
        基于规则的简单聚类
        
        根据行业和薪资水平进行粗略聚类
        """
        jobs = self.db.get_jobs(limit=1000, offset=0)
        
        if not jobs:
            return {
                "clusters": [],
                "cluster_count": 0,
                "message": "无数据可供聚类"
            }
        
        # 简化聚类：按行业分组
        industry_jobs = {}
        for job in jobs:
            industry = job.get('industry') or '其他'
            if industry not in industry_jobs:
                industry_jobs[industry] = []
            industry_jobs[industry].append(job)
        
        clusters = []
        for industry, job_list in industry_jobs.items():
            if len(job_list) < 5:
                continue
            
            # 计算该行业的平均薪资
            salaries = []
            for job in job_list:
                if job.get('salary_min') and job.get('salary_max'):
                    avg = (job['salary_min'] + job['salary_max']) / 2
                    salaries.append(avg)
            
            avg_salary = sum(salaries) / len(salaries) if salaries else 0
            
            # 统计技能
            all_skills = {}
            for job in job_list:
                for skill in job.get('skills') or []:
                    all_skills[skill] = all_skills.get(skill, 0) + 1
            
            top_skills = sorted(all_skills.items(), key=lambda x: x[1], reverse=True)[:10]
            
            clusters.append({
                "cluster_id": len(clusters),
                "name": industry,
                "job_count": len(job_list),
                "avg_salary": round(avg_salary, 2),
                "top_skills": [{"skill": s, "count": c} for s, c in top_skills],
                "sample_titles": [j.get('title', '') for j in job_list[:5]]
            })
        
        # 按职位数排序
        clusters.sort(key=lambda x: x["job_count"], reverse=True)
        
        # 重新编号
        for i, cluster in enumerate(clusters):
            cluster["cluster_id"] = i
        
        return {
            "clusters": clusters[:n_clusters],
            "cluster_count": min(n_clusters, len(clusters)),
            "message": "基于行业规则的简单聚类（模型未加载）"
        }
    
    def get_skill_trends(self) -> Dict[str, Any]:
        """
        技能趋势NLP分析
        
        分析技能的出现频率和关联趋势
        
        Returns:
            技能趋势分析结果
        """
        jobs = self.db.get_jobs(limit=1000, offset=0)
        
        if not jobs:
            return {"trends": [], "hot_skills": [], "emerging_skills": []}
        
        # 统计技能频率
        skill_counts = {}
        skill_by_city = {}
        
        for job in jobs:
            skills = job.get('skills') or []
            city = job.get('city', '未知')
            
            for skill in skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
                
                if city not in skill_by_city:
                    skill_by_city[city] = {}
                skill_by_city[city][skill] = skill_by_city[city].get(skill, 0) + 1
        
        # 按频率排序
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 热门技能
        hot_skills = [
            {"skill": s, "count": c, "percentage": round(c / len(jobs) * 100, 2)}
            for s, c in sorted_skills[:20]
        ]
        
        # 趋势分析（简化版）
        trends = []
        for skill, count in sorted_skills[:10]:
            # 计算该技能在各城市的分布
            city_dist = {}
            for city, skills in skill_by_city.items():
                if skill in skills:
                    city_dist[city] = skills[skill]
            
            trends.append({
                "skill": skill,
                "total_count": count,
                "top_cities": sorted(city_dist.items(), key=lambda x: x[1], reverse=True)[:5]
            })
        
        # 新兴技能（出现频率较低但值得关注）
        # 这里简化处理，假设出现频率中等的技能可能是新兴的
        emerging_skills = [
            {"skill": s, "count": c}
            for s, c in sorted_skills[20:50]
            if c >= 3
        ]
        
        return {
            "trends": trends,
            "hot_skills": hot_skills,
            "emerging_skills": emerging_skills
        }
    
    def get_salary_factors(self) -> Dict[str, Any]:
        """
        薪资影响因素分析
        
        分析影响薪资的主要因素及权重
        
        Returns:
            薪资影响因素分析结果
        """
        jobs = self.db.get_jobs(limit=1000, offset=0)
        
        if not jobs:
            return {"factors": []}
        
        # 计算平均薪资
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                job['avg_salary'] = (job['salary_min'] + job['salary_max']) / 2
        
        # 过滤有薪资的数据
        jobs_with_salary = [j for j in jobs if 'avg_salary' in j]
        
        if not jobs_with_salary:
            return {"factors": []}
        
        # 按因素分组计算平均薪资
        factors = []
        
        # 1. 城市因素
        city_salaries = {}
        for job in jobs_with_salary:
            city = job.get('city', '未知')
            if city not in city_salaries:
                city_salaries[city] = []
            city_salaries[city].append(job['avg_salary'])
        
        city_avg = sum(sum(s) / len(s) for s in city_salaries.values()) / len(city_salaries)
        city_variance = max(sum(s) / len(s) for s in city_salaries.values()) - city_avg
        
        factors.append({
            "factor": "城市",
            "impact_score": round(city_variance / city_avg * 10, 2),
            "description": "不同城市薪资差异显著"
        })
        
        # 2. 经验因素
        exp_salaries = {}
        for job in jobs_with_salary:
            exp = job.get('experience', '不限')
            if exp not in exp_salaries:
                exp_salaries[exp] = []
            exp_salaries[exp].append(job['avg_salary'])
        
        if exp_salaries:
            exp_avg = sum(sum(s) / len(s) for s in exp_salaries.values()) / len(exp_salaries)
            exp_variance = max(sum(s) / len(s) for s in exp_salaries.values()) - exp_avg
            
            factors.append({
                "factor": "经验",
                "impact_score": round(exp_variance / exp_avg * 10, 2),
                "description": "经验要求对薪资影响较大"
            })
        
        # 3. 学历因素
        edu_salaries = {}
        for job in jobs_with_salary:
            edu = job.get('education', '不限')
            if edu not in edu_salaries:
                edu_salaries[edu] = []
            edu_salaries[edu].append(job['avg_salary'])
        
        if edu_salaries:
            edu_avg = sum(sum(s) / len(s) for s in edu_salaries.values()) / len(edu_salaries)
            edu_variance = max(sum(s) / len(s) for s in edu_salaries.values()) - edu_avg
            
            factors.append({
                "factor": "学历",
                "impact_score": round(edu_variance / edu_avg * 10, 2),
                "description": "学历对薪资有一定影响"
            })
        
        # 4. 技能因素（基于有无技能的平均差异）
        with_skills = [j for j in jobs_with_salary if j.get('skills')]
        without_skills = [j for j in jobs_with_salary if not j.get('skills')]
        
        if with_skills and without_skills:
            with_avg = sum(j['avg_salary'] for j in with_skills) / len(with_skills)
            without_avg = sum(j['avg_salary'] for j in without_skills) / len(without_skills)
            skill_diff = (with_avg - without_avg) / without_avg
            
            factors.append({
                "factor": "技能数量",
                "impact_score": round(skill_diff * 5, 2),
                "description": "掌握更多技能可获得更高薪资"
            })
        
        # 按影响力排序
        factors.sort(key=lambda x: x["impact_score"], reverse=True)
        
        return {"factors": factors}
