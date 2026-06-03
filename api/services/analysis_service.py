# 分析计算服务层
"""
数据分析计算服务
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from storage.database import db_manager


class AnalysisService:
    """
    数据分析服务
    
    提供薪资、城市、技能、行业等维度的分析计算
    """
    
    def __init__(self):
        """初始化服务"""
        self.db = db_manager
    
    def _load_data(
        self,
        city: Optional[str] = None,
        industry: Optional[str] = None,
        source: Optional[str] = None
    ) -> List[Dict]:
        """
        加载并筛选数据
        
        Args:
            city: 城市筛选
            industry: 行业筛选
            source: 数据来源
            
        Returns:
            职位数据列表
        """
        jobs = self.db.get_jobs(
            city=city,
            industry=industry,
            source=source,
            limit=10000,
            offset=0
        )
        return jobs
    
    def analyze_salary(
        self,
        city: Optional[str] = None,
        industry: Optional[str] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        薪资分析
        
        Args:
            city: 城市筛选
            industry: 行业筛选
            source: 数据来源
            
        Returns:
            薪资分析结果
        """
        jobs = self._load_data(city=city, industry=industry, source=source)
        
        if not jobs:
            return {
                "basic_stats": {},
                "distribution": [],
                "by_city": [],
                "by_industry": [],
                "by_experience": []
            }
        
        # 计算平均薪资
        salaries = []
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                avg = (job['salary_min'] + job['salary_max']) / 2
                salaries.append({
                    **job,
                    'avg_salary': avg
                })
        
        if not salaries:
            return {
                "basic_stats": {"count": 0},
                "distribution": [],
                "by_city": [],
                "by_industry": [],
                "by_experience": []
            }
        
        # 基本统计
        salary_values = [s['avg_salary'] for s in salaries]
        salary_values.sort()
        
        basic_stats = {
            "count": len(salary_values),
            "mean": round(sum(salary_values) / len(salary_values), 2),
            "median": round(salary_values[len(salary_values) // 2], 2),
            "min": round(min(salary_values), 2),
            "max": round(max(salary_values), 2),
            "q25": round(salary_values[len(salary_values) // 4], 2),
            "q75": round(salary_values[len(salary_values) * 3 // 4], 2)
        }
        
        # 薪资分布（按区间）
        bins = [0, 5, 10, 15, 20, 25, 30, 40, 50, 100]
        distribution = []
        for i in range(len(bins) - 1):
            count = sum(1 for s in salary_values if bins[i] <= s < bins[i + 1])
            distribution.append({
                "range": f"{bins[i]}-{bins[i + 1]}K",
                "count": count,
                "percentage": round(count / len(salary_values) * 100, 2)
            })
        # 处理50K以上
        count_50plus = sum(1 for s in salary_values if s >= 50)
        if count_50plus > 0:
            distribution.append({
                "range": "50K+",
                "count": count_50plus,
                "percentage": round(count_50plus / len(salary_values) * 100, 2)
            })
        
        # 按城市统计
        city_salary = {}
        for job in salaries:
            city = job.get('city', '未知')
            if city not in city_salary:
                city_salary[city] = []
            city_salary[city].append(job['avg_salary'])
        
        by_city = [
            {
                "city": city,
                "count": len(salary_list),
                "avg_salary": round(sum(salary_list) / len(salary_list), 2)
            }
            for city, salary_list in sorted(
                city_salary.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )[:20]
        ]
        
        # 按行业统计
        industry_salary = {}
        for job in salaries:
            industry = job.get('industry') or '未知'
            if industry not in industry_salary:
                industry_salary[industry] = []
            industry_salary[industry].append(job['avg_salary'])
        
        by_industry = [
            {
                "industry": industry,
                "count": len(salary_list),
                "avg_salary": round(sum(salary_list) / len(salary_list), 2)
            }
            for industry, salary_list in sorted(
                industry_salary.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )[:20]
        ]
        
        # 按经验统计
        exp_order = ['不限', '应届/在校', '1年以下', '1-3年', '3-5年', '5-10年', '10年以上']
        exp_salary = {}
        for job in salaries:
            exp = job.get('experience') or '不限'
            if exp not in exp_salary:
                exp_salary[exp] = []
            exp_salary[exp].append(job['avg_salary'])
        
        by_experience = []
        for exp in exp_order:
            if exp in exp_salary:
                salary_list = exp_salary[exp]
                by_experience.append({
                    "experience": exp,
                    "count": len(salary_list),
                    "avg_salary": round(sum(salary_list) / len(salary_list), 2)
                })
        
        return {
            "basic_stats": basic_stats,
            "distribution": distribution,
            "by_city": by_city,
            "by_industry": by_industry,
            "by_experience": by_experience
        }
    
    def analyze_cities(self, limit: int = 20) -> Dict[str, Any]:
        """
        城市分析
        
        Args:
            limit: 返回数量限制
            
        Returns:
            城市分析结果
        """
        jobs = self.db.get_jobs(limit=10000, offset=0)
        
        if not jobs:
            return {"job_counts": [], "avg_salary": [], "top_skills": []}
        
        # 计算平均薪资
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                job['avg_salary'] = (job['salary_min'] + job['salary_max']) / 2
        
        # 职位数统计
        city_counts = {}
        city_salaries = {}
        city_skills = {}
        
        for job in jobs:
            city = job.get('city', '未知')
            
            # 计数
            city_counts[city] = city_counts.get(city, 0) + 1
            
            # 薪资
            if 'avg_salary' in job:
                if city not in city_salaries:
                    city_salaries[city] = []
                city_salaries[city].append(job['avg_salary'])
            
            # 技能
            skills = job.get('skills') or []
            if city not in city_skills:
                city_skills[city] = {}
            for skill in skills:
                city_skills[city][skill] = city_skills[city].get(skill, 0) + 1
        
        # 排序并限制数量
        job_counts = sorted(
            [{"city": c, "count": n} for c, n in city_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:limit]
        
        avg_salary = [
            {
                "city": c,
                "avg_salary": round(sum(s) / len(s), 2),
                "count": len(s)
            }
            for c, s in city_salaries.items()
        ]
        avg_salary.sort(key=lambda x: x["avg_salary"], reverse=True)
        
        # 各城市热门技能
        top_skills = []
        for city in [c["city"] for c in job_counts[:10]]:
            skills = city_skills.get(city, {})
            sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)[:5]
            top_skills.append({
                "city": city,
                "skills": [{"skill": s, "count": c} for s, c in sorted_skills]
            })
        
        return {
            "job_counts": job_counts,
            "avg_salary": avg_salary,
            "top_skills": top_skills
        }
    
    def analyze_skills(self, limit: int = 50) -> Dict[str, Any]:
        """
        技能分析
        
        Args:
            limit: 返回技能数量限制
            
        Returns:
            技能分析结果
        """
        jobs = self.db.get_jobs(limit=10000, offset=0)
        
        if not jobs:
            return {"top_skills": [], "skill_correlations": [], "skill_trends": []}
        
        # 统计技能频率
        skill_counts = {}
        for job in jobs:
            skills = job.get('skills') or []
            for skill in skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        # 高频技能排行
        top_skills = sorted(
            [{"skill": s, "count": c} for s, c in skill_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:limit]
        
        # 计算技能共现（关联分析）
        skill_correlations = []
        all_skills = [set(job.get('skills') or []) for job in jobs]
        
        # 取前20个热门技能做关联分析
        top_skill_names = [s["skill"] for s in top_skills[:20]]
        
        for i, skill1 in enumerate(top_skill_names):
            for skill2 in top_skill_names[i + 1:]:
                co_count = sum(1 for skills in all_skills if skill1 in skills and skill2 in skills)
                if co_count > 0:
                    skill_correlations.append({
                        "skill1": skill1,
                        "skill2": skill2,
                        "co_count": co_count
                    })
        
        # 按共现次数排序
        skill_correlations.sort(key=lambda x: x["co_count"], reverse=True)
        skill_correlations = skill_correlations[:50]
        
        # 技能趋势（简化版，基于当前数据）
        skill_trends = top_skills[:10]
        
        return {
            "top_skills": top_skills,
            "skill_correlations": skill_correlations,
            "skill_trends": skill_trends
        }
    
    def analyze_industries(self, limit: int = 20) -> Dict[str, Any]:
        """
        行业分析
        
        Args:
            limit: 返回数量限制
            
        Returns:
            行业分析结果
        """
        jobs = self.db.get_jobs(limit=10000, offset=0)
        
        if not jobs:
            return {"industries": []}
        
        # 计算平均薪资
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                job['avg_salary'] = (job['salary_min'] + job['salary_max']) / 2
        
        # 按行业统计
        industry_stats = {}
        for job in jobs:
            industry = job.get('industry') or '未知'
            if industry not in industry_stats:
                industry_stats[industry] = {
                    "industry": industry,
                    "count": 0,
                    "salaries": []
                }
            industry_stats[industry]["count"] += 1
            if 'avg_salary' in job:
                industry_stats[industry]["salaries"].append(job['avg_salary'])
        
        industries = []
        for industry, stats in industry_stats.items():
            result = {
                "industry": industry,
                "count": stats["count"]
            }
            if stats["salaries"]:
                result["avg_salary"] = round(sum(stats["salaries"]) / len(stats["salaries"]), 2)
                result["median_salary"] = round(sorted(stats["salaries"])[len(stats["salaries"]) // 2], 2)
            industries.append(result)
        
        industries.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "industries": industries[:limit]
        }
    
    def analyze_experience(self) -> Dict[str, Any]:
        """
        经验要求分析
        
        Returns:
            经验要求分析结果
        """
        jobs = self.db.get_jobs(limit=10000, offset=0)
        
        if not jobs:
            return {"experiences": []}
        
        # 计算平均薪资
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                job['avg_salary'] = (job['salary_min'] + job['salary_max']) / 2
        
        # 经验顺序
        exp_order = ['不限', '应届/在校', '1年以下', '1-3年', '3-5年', '5-10年', '10年以上']
        
        # 按经验统计
        exp_stats = {}
        for job in jobs:
            exp = job.get('experience') or '不限'
            if exp not in exp_stats:
                exp_stats[exp] = {
                    "experience": exp,
                    "count": 0,
                    "salaries": []
                }
            exp_stats[exp]["count"] += 1
            if 'avg_salary' in job:
                exp_stats[exp]["salaries"].append(job['avg_salary'])
        
        experiences = []
        for exp in exp_order:
            if exp in exp_stats:
                stats = exp_stats[exp]
                result = {
                    "experience": exp,
                    "count": stats["count"]
                }
                if stats["salaries"]:
                    result["avg_salary"] = round(sum(stats["salaries"]) / len(stats["salaries"]), 2)
                experiences.append(result)
        
        return {"experiences": experiences}
    
    def analyze_education(self) -> Dict[str, Any]:
        """
        学历要求分析
        
        Returns:
            学历要求分析结果
        """
        jobs = self.db.get_jobs(limit=10000, offset=0)
        
        if not jobs:
            return {"educations": []}
        
        # 计算平均薪资
        for job in jobs:
            if job.get('salary_min') and job.get('salary_max'):
                job['avg_salary'] = (job['salary_min'] + job['salary_max']) / 2
        
        # 学历顺序
        edu_order = ['不限', '高中/中专', '大专', '本科', '硕士', '博士']
        
        # 按学历统计
        edu_stats = {}
        for job in jobs:
            edu = job.get('education') or '不限'
            if edu not in edu_stats:
                edu_stats[edu] = {
                    "education": edu,
                    "count": 0,
                    "salaries": []
                }
            edu_stats[edu]["count"] += 1
            if 'avg_salary' in job:
                edu_stats[edu]["salaries"].append(job['avg_salary'])
        
        educations = []
        for edu in edu_order:
            if edu in edu_stats:
                stats = edu_stats[edu]
                result = {
                    "education": edu,
                    "count": stats["count"]
                }
                if stats["salaries"]:
                    result["avg_salary"] = round(sum(stats["salaries"]) / len(stats["salaries"]), 2)
                educations.append(result)
        
        return {"educations": educations}
