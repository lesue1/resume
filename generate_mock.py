"""生成 100 条模拟简历数据"""
import random
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'resume_screening.db')

# ── 数据池 ──
SURNAMES = ['张','王','李','赵','陈','刘','黄','周','吴','郑','冯','孙','马','朱','胡','杨','何','高','林','罗','郭','梁','宋','唐','许','韩','邓','沈','彭','苏','蒋','蔡','潘','魏','薛','丁','余','叶','阎','汪']
GIVEN = ['伟','强','敏','静','丽','磊','洋','勇','军','杰','涛','明','超','秀英','华','慧','鑫','桂英','佳','宇','浩','然','博','文','思','雨','雪','晨','阳','宁','涵','子轩','一鸣','天宇','浩然','欣怡','梓涵','奕辰','若溪','诗涵']

CITIES = ['北京','上海','深圳','杭州','广州','成都','南京','武汉','苏州','西安','长沙','重庆','厦门','合肥','郑州']
SCHOOLS = [
    ('清华大学','985'), ('北京大学','985'), ('浙江大学','985'), ('上海交通大学','985'), ('复旦大学','985'),
    ('南京大学','985'), ('华中科技大学','985'), ('武汉大学','985'), ('中山大学','985'), ('四川大学','985'),
    ('电子科技大学','985'), ('西安交通大学','985'), ('哈尔滨工业大学','985'), ('同济大学','985'), ('北京邮电大学','211'),
    ('华南理工大学','985'), ('东南大学','985'), ('北京航空航天大学','985'), ('中国人民大学','985'), ('南开大学','985'),
    ('深圳大学','双非'), ('杭州电子科技大学','双非'), ('南京邮电大学','双非'), ('重庆邮电大学','双非'), ('广东工业大学','双非'),
]

DEGREES = ['本科','硕士','博士','大专']
MAJORS = ['计算机科学与技术','软件工程','人工智能','数据科学与大数据','电子信息工程','通信工程','自动化','网络工程','信息安全','数学与应用数学']

COMPANIES = [
    ('阿里巴巴','杭州'), ('腾讯','深圳'), ('字节跳动','北京'), ('美团','北京'), ('拼多多','上海'),
    ('京东','北京'), ('百度','北京'), ('网易','杭州'), ('快手','北京'), ('小红书','上海'),
    ('华为','深圳'), ('小米','北京'), ('哔哩哔哩','上海'), ('滴滴','北京'), ('蚂蚁集团','杭州'),
    ('微软','北京'), ('谷歌','上海'), ('Shopee','深圳'), ('Zoom','杭州'), ('Thoughtworks','西安'),
    ('中兴','深圳'), ('科大讯飞','合肥'), ('商汤科技','北京'), ('旷视科技','北京'), ('大疆','深圳'),
    ('蔚来','上海'), ('理想汽车','北京'), ('小鹏汽车','广州'), ('SHEIN','广州'), ('米哈游','上海'),
]

POSITIONS = [
    'Python后端开发工程师','Java开发工程师','Go后端工程师','前端开发工程师','全栈工程师',
    '算法工程师','NLP工程师','计算机视觉工程师','推荐算法工程师','数据工程师',
    '数据分析师','大数据开发工程师','DevOps工程师','测试开发工程师','安全工程师',
    'iOS开发工程师','Android开发工程师','C++开发工程师','架构师','技术经理',
]

SKILLS_POOL = ['Python','Java','Go','C++','Rust','JavaScript','TypeScript','React','Vue','Node.js',
    'Django','Flask','Spring Boot','MySQL','PostgreSQL','MongoDB','Redis','Kafka','RabbitMQ',
    'Docker','Kubernetes','AWS','Linux','Git','TensorFlow','PyTorch','Spark','Flink','Hadoop',
    'Nginx','Elasticsearch','Prometheus','Grafana','CI/CD','gRPC','GraphQL','微服务','分布式系统']

TECH_DIRS = ['后端','前端','算法','数据','DevOps','安全','移动端','全栈']
SOURCES = ['内推','Boss直聘','猎头','校招','脉脉','LinkedIn','拉勾','官网投递']

STATUSES = [
    '筛选','筛选','筛选','筛选','筛选','筛选',   # 6/20 = 30%
    '评估','评估','评估','评估',                   # 4/20 = 20%
    '一面','一面','一面',                          # 3/20 = 15%
    '二面','二面',                                 # 2/20 = 10%
    '三面',                                       # 1/20 = 5%
    'HR面',                                       # 1/20 = 5%
    'Offer沟通','Offer沟通',                       # 2/20 = 10%
    '录用',                                       # 1/20 = 5%
]

SALARY_RANGES = [
    ('10K','15K'), ('15K','20K'), ('18K','25K'), ('20K','30K'), ('25K','35K'),
    ('30K','40K'), ('35K','45K'), ('40K','55K'), ('50K','70K'), ('18K','22K'),
]

def rand_phone():
    prefixes = ['13','15','17','18','19']
    return random.choice(prefixes) + ''.join(str(random.randint(0,9)) for _ in range(9))

def rand_email(name):
    domains = ['gmail.com','qq.com','163.com','outlook.com','foxmail.com','126.com']
    return f"{name.lower()}{random.randint(1,999)}@{random.choice(domains)}"

def gen_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)

def gen_skills():
    n = random.randint(3, 8)
    return '，'.join(random.sample(SKILLS_POOL, n))

def gen_resume_text(row):
    parts = []
    parts.append(f"姓名：{row[1]}")
    parts.append(f"性别：{row[2]} | 年龄：{row[3]}")
    parts.append(f"手机：{row[4]} | 邮箱：{row[5]}")
    parts.append(f"城市：{row[6]}")
    parts.append(f"毕业院校：{row[7]} | 学历：{row[8]} | 专业：{row[9]}")
    parts.append(f"毕业年份：{row[10]}")
    parts.append(f"当前公司：{row[11]} | 职位：{row[12]}")
    parts.append(f"工作年限：{row[13]}")
    parts.append(f"当前薪资：{row[15]} | 期望薪资：{row[16]}")
    parts.append(f"技能：{row[17]}")
    parts.append(f"意向方向：{row[18]} | 来源：{row[19]}")
    parts.append(f"目标岗位：{row[20]}")
    return '\n'.join(parts)

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 清空旧数据
    cur.execute("DELETE FROM resumes")
    cur.execute("DELETE FROM evaluations")
    conn.commit()

    rows = []
    for i in range(100):
        code = f'MOCK{1000+i}'
        name = gen_name()
        gender = random.choice(['男','女'])
        age = str(random.randint(22, 35))
        phone = rand_phone()
        email = rand_email(name)
        city = random.choice(CITIES)
        school, _ = random.choice(SCHOOLS)
        degree = random.choice(DEGREES)
        major = random.choice(MAJORS)
        grad_year = str(random.randint(2015, 2025))
        company, _ = random.choice(COMPANIES)
        position = random.choice(POSITIONS)
        work_years = random.choice(['应届','1年','2年','3年','4年','5年','6年','7年','8年','10年'])
        emp_status = random.choice(['在职','离职','实习'])
        cur_salary = random.choice(SALARY_RANGES)
        exp_salary = random.choice(SALARY_RANGES)
        skills = gen_skills()
        tech_dir = random.choice(TECH_DIRS)
        source = random.choice(SOURCES)
        target = random.choice(POSITIONS)
        status = random.choice(STATUSES)
        notes = ''
        has_papers = 1 if random.random() < 0.08 else 0  # 8% 有顶会

        row = (code, name, gender, age, phone, email, city, school, degree, major,
               grad_year, company, position, work_years, emp_status,
               cur_salary[0], exp_salary[0], skills, tech_dir, source, target,
               status, notes, '', has_papers)
        rows.append(row)

    cur.executemany("""
        INSERT INTO resumes (unique_code, name, gender, age, phone, email, city, school,
          degree, major, graduation_year, current_company, current_position,
          work_years, employment_status, current_salary, expected_salary,
          skills, tech_direction, source, target_position, interview_status,
          hr_notes, resume_text, has_top_papers)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)

    # 给一部分人生成简历正文
    for idx, row in enumerate(rows):
        name = row[1]
        text = f"""个人简历

{name} | {row[2]} | {row[3]}岁
{row[4]} | {row[5]}
现居{row[6]}

教育背景
{row[9]} {row[8]} | {row[7]} | {row[10]}年毕业

工作经历
{row[11]} | {row[12]} | 工作{row[13]}

技能特长
{row[17]}

求职意向
{row[20]} | 期望薪资 {row[16]}
"""
        cur.execute("UPDATE resumes SET resume_text=? WHERE unique_code=?", (text, row[0]))

    conn.commit()
    conn.close()

    # 统计
    print(f"[OK] 已生成 100 条模拟简历")
    from collections import Counter
    dist = Counter(r[21] for r in rows)
    for name in ['筛选','评估','一面','二面','三面','HR面','Offer沟通','录用']:
        print(f"    {name}: {dist.get(name, 0)}")

if __name__ == '__main__':
    main()
