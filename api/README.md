# FastAPI后端接口文档

## 快速启动

### 1. 安装依赖

```bash
cd job_analysis_platform
pip install -r requirements.txt
```

### 2. 启动服务

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 访问API文档

启动后访问: http://localhost:8000/docs

## API端点

### 系统接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | 根路径信息 |
| GET | `/api/info` | API信息 |

### 职位管理 (/api/jobs)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/jobs` | 分页查询职位列表 |
| GET | `/api/jobs/{id}` | 职位详情 |
| GET | `/api/jobs/search` | 全文搜索 |
| GET | `/api/jobs/stats` | 职位统计概览 |
| GET | `/api/jobs/distinct` | 获取筛选项值 |
| DELETE | `/api/jobs/{id}` | 删除职位 |

#### 查询参数示例

```
GET /api/jobs?city=北京&source=zhilian&page=1&page_size=20
GET /api/jobs/search?q=Python&page=1&page_size=20
GET /api/jobs/distinct?field=city
```

### 数据分析 (/api/analysis)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/analysis/salary` | 薪资分析 |
| GET | `/api/analysis/city` | 城市分析 |
| GET | `/api/analysis/skill` | 技能分析 |
| GET | `/api/analysis/industry` | 行业分析 |
| GET | `/api/analysis/experience` | 经验要求分析 |
| GET | `/api/analysis/education` | 学历要求分析 |

#### 查询参数示例

```
GET /api/analysis/salary?city=北京&industry=互联网
GET /api/analysis/city?limit=20
GET /api/analysis/skill?limit=50
```

### AI分析 (/api/ai)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/ai/predict-salary` | 薪资预测 |
| GET | `/api/ai/clusters` | 岗位聚类 |
| GET | `/api/ai/skill-trends` | 技能趋势 |
| GET | `/api/ai/salary-factors` | 薪资影响因素 |

#### 请求示例

```json
POST /api/ai/predict-salary
{
    "city": "北京",
    "skills": ["Python", "SQL", "机器学习"],
    "education": "本科",
    "experience": "3-5年"
}
```

### 爬虫管理 (/api/crawler)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/crawler/start` | 启动爬虫 |
| GET | `/api/crawler/status` | 爬虫状态 |
| GET | `/api/crawler/sources` | 可用数据源 |
| GET | `/api/crawler/tasks` | 任务列表 |
| GET | `/api/crawler/task/{task_id}` | 任务详情 |

#### 请求示例

```json
POST /api/crawler/start
{
    "source": "boss",
    "city": "北京",
    "keyword": "Python"
}
```

## 统一响应格式

所有API返回统一格式:

```json
{
    "code": 200,
    "message": "ok",
    "data": { ... }
}
```

错误时:
```json
{
    "code": 404,
    "message": "职位不存在",
    "data": null
}
```

## 分页响应格式

```json
{
    "items": [...],
    "pagination": {
        "total": 5824,
        "page": 1,
        "page_size": 20,
        "total_pages": 292
    }
}
```
