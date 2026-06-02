"""数据回填脚本：从职位标题中提取城市、经验、学历信息，补全数据库中的未知字段。"""
import sys, re
sys.path.insert(0, '/root/projects/job_analysis_platform')
from storage.database import db_manager
from sqlalchemy import text

# ---- 城市关键词（出现在标题中的城市名） ----
CITY_PATTERNS = [
    (re.compile(r'北京|首都'), '北京'),
    (re.compile(r'上海|魔都|沪'), '上海'),
    (re.compile(r'广州'), '广州'),
    (re.compile(r'深圳|深'), '深圳'),
    (re.compile(r'杭州'), '杭州'),
    (re.compile(r'成都'), '成都'),
    (re.compile(r'武汉'), '武汉'),
    (re.compile(r'西安'), '西安'),
    (re.compile(r'南京'), '南京'),
    (re.compile(r'苏州'), '苏州'),
    (re.compile(r'重庆'), '重庆'),
    (re.compile(r'天津'), '天津'),
    (re.compile(r'长沙'), '长沙'),
    (re.compile(r'郑州'), '郑州'),
    (re.compile(r'东莞'), '东莞'),
    (re.compile(r'青岛'), '青岛'),
    (re.compile(r'济南'), '济南'),
    (re.compile(r'合肥'), '合肥'),
    (re.compile(r'福州'), '福州'),
    (re.compile(r'厦门'), '厦门'),
    (re.compile(r'宁波'), '宁波'),
    (re.compile(r'无锡'), '无锡'),
    (re.compile(r'佛山'), '佛山'),
    (re.compile(r'大连'), '大连'),
    (re.compile(r'沈阳'), '沈阳'),
    (re.compile(r'昆明'), '昆明'),
    (re.compile(r'南宁'), '南宁'),
    (re.compile(r'南昌'), '南昌'),
    (re.compile(r'廊坊'), '廊坊'),
    (re.compile(r'临沂'), '临沂'),
    (re.compile(r'长春'), '长春'),
    (re.compile(r'哈尔滨'), '哈尔滨'),
    (re.compile(r'石家庄'), '石家庄'),
    (re.compile(r'太原'), '太原'),
    (re.compile(r'常州'), '常州'),
    (re.compile(r'惠州'), '惠州'),
    (re.compile(r'珠海'), '珠海'),
]

# ---- 经验关键词从标题提取 ----
EXP_PATTERNS = [
    (re.compile(r'应届|实习[^训]|管培生|培训生|校招|学徒|储备|暑假工'), '应届生'),
    (re.compile(r'初级|助理|专员|文员|普工|操作工|配送|骑手|店员|服务员|客服|保安|保洁|叉车工|司机|搬运工|钟点工|日结|临时|短期'), '1年以内'),
    (re.compile(r'高级|资深|主管|组长|领班'), '3-5年'),
    (re.compile(r'专家|架构师|总监|经理|负责人|主任|店长|厂长'), '5-10年'),
    (re.compile(r'首席|VP|副总裁|CTO|CEO|COO|CFO|总经理'), '10年以上'),
]

# ---- 学历关键词 ----
EDU_PATTERNS = [
    (re.compile(r'博士|博士后|博后'), '博士'),
    (re.compile(r'硕士|研究生'), '硕士'),
    (re.compile(r'本科|统招|全日制'), '本科'),
    (re.compile(r'大专|专科|高职'), '大专'),
    (re.compile(r'高中|中专|中技'), '高中'),
    (re.compile(r'初中'), '初中及以下'),
]


def extract_city(title):
    """从标题提取城市名"""
    for pattern, city in CITY_PATTERNS:
        if pattern.search(title):
            return city
    return None


def extract_experience(title):
    """从标题提取经验档位"""
    for pattern, exp in EXP_PATTERNS:
        if pattern.search(title):
            return exp
    return None


def extract_education(title):
    """从标题提取学历"""
    for pattern, edu in EDU_PATTERNS:
        if pattern.search(title):
            return edu
    return None


# ---- 执行回填 ----
def main():
    with db_manager.get_session() as s:
        jobs = s.execute(text(
            "SELECT id, title, city, experience, education FROM jobs "
            "WHERE city='未知' OR experience IS NULL OR education IS NULL"
        )).fetchall()

        print(f'需要处理的记录: {len(jobs)}')

        city_cnt = 0
        exp_cnt = 0
        edu_cnt = 0

        for i, job in enumerate(jobs):
            job_id, title, cur_city, cur_exp, cur_edu = job

            updates = []
            params = {}

            # 城市回填
            if cur_city == '未知':
                c = extract_city(title)
                if c:
                    updates.append("city = :city")
                    params['city'] = c
                    city_cnt += 1

            # 经验回填
            if cur_exp is None:
                e = extract_experience(title)
                if e:
                    updates.append("experience = :exp")
                    params['exp'] = e
                    exp_cnt += 1

            # 学历回填
            if cur_edu is None:
                ed = extract_education(title)
                if ed:
                    updates.append("education = :edu")
                    params['edu'] = ed
                    edu_cnt += 1

            if updates:
                params['id'] = job_id
                sql_str = "UPDATE jobs SET " + ", ".join(updates) + " WHERE id = :id"
                s.execute(text(sql_str), params)

            if (i + 1) % 500 == 0:
                s.flush()
                print(f'  进度: {i+1}/{len(jobs)} | city={city_cnt} exp={exp_cnt} edu={edu_cnt}')

        s.flush()
        print(f'\n回填完成:')
        print(f'  城市: {city_cnt} 条')
        print(f'  经验: {exp_cnt} 条')
        print(f'  学历: {edu_cnt} 条')

        # 确认结果
        r = s.execute(text("SELECT COUNT(*) FROM jobs WHERE city='未知'")).fetchone()[0]
        print(f'  剩余未知城市: {r} 条')
        r = s.execute(text("SELECT COUNT(*) FROM jobs WHERE experience IS NULL")).fetchone()[0]
        print(f'  剩余空经验: {r} 条')
        r = s.execute(text("SELECT COUNT(*) FROM jobs WHERE education IS NULL")).fetchone()[0]
        print(f'  剩余空学历: {r} 条')

    print('回填脚本执行完毕')


if __name__ == '__main__':
    main()
