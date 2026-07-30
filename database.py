"""
database.py — 所有数据库操作
SQLite 是 Python 内置的，文件就是数据库，不需要装任何东西。
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime
import config

DB_NAME = config.DB_NAME


def get_conn():
    """获取数据库连接。
    sqlite3.connect() 打开文件，如果文件不存在会自动创建。
    这就是 SQLite 方便的地方——"建库"不需要额外步骤。
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # 让查询结果可以用 row['列名'] 访问
    return conn


# =============================================================================
# 初始化
# =============================================================================

def init_db():
    """建表。CREATE TABLE IF NOT EXISTS = 表不存在才建，已存在就跳过。
    所以每次启动都可以调用，不会覆盖数据。
    """
    conn = get_conn()
    cur = conn.cursor()  # cursor 是执行 SQL 的"笔"

    # ---------- 表1：AI 评分记录 ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT,
            email TEXT,
            phone TEXT,
            job_title TEXT,
            total_score REAL,
            scores_json TEXT,
            jd_text TEXT,
            resume_text TEXT,
            interview_status TEXT DEFAULT '筛选',
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---------- 表2：简历库（23字段，对接旧系统数据） ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_code TEXT UNIQUE,
            name TEXT, gender TEXT, age TEXT, phone TEXT, email TEXT,
            city TEXT, school TEXT, degree TEXT, major TEXT,
            graduation_year TEXT, current_company TEXT, current_position TEXT,
            work_years TEXT, employment_status TEXT,
            current_salary TEXT, expected_salary TEXT,
            skills TEXT, tech_direction TEXT, source TEXT,
            target_position TEXT, interview_status TEXT DEFAULT '筛选',
            hr_notes TEXT, resume_text TEXT,
            has_top_papers INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---------- 表3：岗位库 ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            jd_text TEXT,
            requirements TEXT,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---------- 表4：招聘管道阶段 ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            color TEXT DEFAULT '#0071e3'
        )
    """)

    # ── 兼容旧表：加 token_info 列（如果还没有） ──
    try:
        cur.execute("ALTER TABLE evaluations ADD COLUMN token_info TEXT DEFAULT ''")
    except:
        pass  # 列已存在

    # ── 兼容旧表：加 file_path 列（存储简历PDF附件路径） ──
    try:
        cur.execute("ALTER TABLE resumes ADD COLUMN file_path TEXT DEFAULT ''")
    except:
        pass

    # ── 索引（加速查询，IF NOT EXISTS 避免重复创建） ──
    cur.execute("CREATE INDEX IF NOT EXISTS idx_resumes_status ON resumes(interview_status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_resumes_degree ON resumes(degree)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_resumes_direction ON resumes(tech_direction)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_resumes_created ON resumes(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_time ON evaluations(evaluated_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at)")

    conn.commit()
    conn.close()
    seed_stages()


# =============================================================================
# 招聘管道阶段管理
# =============================================================================

def seed_stages():
    """首次运行时写入 8 个默认阶段（已存在则跳过）。"""
    defaults = [
        ("筛选", 1, "#6e6e73"),
        ("评估", 2, "#0071e3"),
        ("一面", 3, "#5856d6"),
        ("二面", 4, "#af52de"),
        ("三面", 5, "#ff9500"),
        ("HR面", 6, "#f56300"),
        ("Offer沟通", 7, "#34c759"),
        ("录用", 8, "#30d158"),
    ]
    conn = get_conn()
    for name, order, color in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO pipeline_stages (name, sort_order, color) VALUES (?, ?, ?)",
            (name, order, color),
        )
    conn.commit()
    conn.close()


def get_stages():
    """返回所有阶段，按 sort_order 排序。"""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM pipeline_stages ORDER BY sort_order").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "sort_order": r["sort_order"], "color": r["color"]} for r in rows]


def save_stage(stage_id, name, color, sort_order):
    """新增或更新阶段。stage_id 为空则新增。"""
    conn = get_conn()
    if stage_id:
        # 更新：先查旧名，同步更新 resumes 和 evaluations
        old = conn.execute("SELECT name FROM pipeline_stages WHERE id=?", (stage_id,)).fetchone()
        if old:
            old_name = old[0]
            conn.execute(
                "UPDATE pipeline_stages SET name=?, color=?, sort_order=? WHERE id=?",
                (name, color, sort_order, stage_id),
            )
            if old_name != name:
                conn.execute("UPDATE resumes SET interview_status=? WHERE interview_status=?", (name, old_name))
                conn.execute("UPDATE evaluations SET interview_status=? WHERE interview_status=?", (name, old_name))
    else:
        conn.execute(
            "INSERT INTO pipeline_stages (name, color, sort_order) VALUES (?, ?, ?)",
            (name, color, sort_order),
        )
    conn.commit()
    conn.close()


def delete_stage(stage_id):
    """删除阶段，该阶段下的简历状态置空。"""
    conn = get_conn()
    row = conn.execute("SELECT name FROM pipeline_stages WHERE id=?", (stage_id,)).fetchone()
    if row:
        name = row[0]
        conn.execute("UPDATE resumes SET interview_status='' WHERE interview_status=?", (name,))
        conn.execute("UPDATE evaluations SET interview_status='' WHERE interview_status=?", (name,))
        conn.execute("DELETE FROM pipeline_stages WHERE id=?", (stage_id,))
    conn.commit()
    conn.close()


def reorder_stages(order_list):
    """批量更新排序。order_list 是 [stage_id, ...] 按新顺序排列。"""
    conn = get_conn()
    for i, sid in enumerate(order_list, 1):
        conn.execute("UPDATE pipeline_stages SET sort_order=? WHERE id=?", (i, sid))
    conn.commit()
    conn.close()

def save_job(title, jd_text="", requirements="", department=""):
    """新增或更新岗位。title 相同时更新。"""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing = conn.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE jobs SET jd_text=?, requirements=?, department=?, updated_at=?
            WHERE id=?
        """, (jd_text, requirements, department, now, existing[0]))
    else:
        conn.execute("""
            INSERT INTO jobs (title, jd_text, requirements, department, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, jd_text, requirements, department, now, now))

    conn.commit()
    conn.close()


def get_jobs(search=""):
    """获取所有岗位，支持搜索。"""
    conn = get_conn()
    if search:
        df = pd.read_sql_query(
            "SELECT * FROM jobs WHERE title LIKE ? ORDER BY updated_at DESC",
            conn, params=(f"%{search}%",),
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM jobs ORDER BY updated_at DESC", conn
        )
    conn.close()
    return df


def get_job(job_id):
    """获取单个岗位详情。"""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row:
        return {k: row[k] for k in row.keys()}
    return None


def delete_job(job_id):
    """删除岗位。"""
    conn = get_conn()
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


# =============================================================================
# 评估记录 CRUD
# =============================================================================

def save_evaluation(name, email, phone, job_title, total, scores_dict,
                    jd_text, resume_text, token_info=None):
    """保存一次 AI 评分到数据库。

    参数:
        scores_dict: {'技能匹配度': {'score': 85, 'reason': '...'}, ...}
        token_info: {'prompt': 500, 'completion': 200, 'total': 700} 或 None
    """
    conn = get_conn()
    conn.execute("""
        INSERT INTO evaluations
            (candidate_name, email, phone, job_title, total_score,
             scores_json, jd_text, resume_text, token_info, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name or "未知",
        email or "",
        phone or "",
        job_title or "未指定岗位",
        round(total, 1),
        json.dumps(scores_dict, ensure_ascii=False),
        jd_text or "",
        resume_text or "",
        json.dumps(token_info, ensure_ascii=False) if token_info else "",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    conn.close()


def get_evaluations(limit=100):
    """查询最近 N 条评估记录，返回 DataFrame。
    倒序排列 = 最新的在前面。
    """
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM evaluations ORDER BY evaluated_at DESC LIMIT ?",
        conn,
        params=(limit,),
    )
    conn.close()
    return df


def get_evaluations_for_resume(email, name):
    """根据邮箱或姓名查历史评估记录，按时间倒序。"""
    conn = get_conn()
    # 优先 email 精确匹配；如果 email 为空，用姓名匹配
    if email:
        df = pd.read_sql_query(
            "SELECT * FROM evaluations WHERE email = ? ORDER BY evaluated_at DESC",
            conn, params=(email,),
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM evaluations WHERE candidate_name = ? ORDER BY evaluated_at DESC",
            conn, params=(name,),
        )
    conn.close()
    return df



# =============================================================================
# 简历库 CRUD
# =============================================================================

def save_resume(data: dict):
    """插入或更新一份简历。

    INSERT OR REPLACE: 如果 unique_code 已存在就更新，否则插入。
    """
    conn = get_conn()
    fields = [
        'unique_code', 'name', 'gender', 'age', 'phone', 'email', 'city',
        'school', 'degree', 'major', 'graduation_year', 'current_company',
        'current_position', 'work_years', 'employment_status',
        'current_salary', 'expected_salary',
        'skills', 'tech_direction', 'source', 'target_position',
        'interview_status', 'hr_notes', 'resume_text', 'has_top_papers', 'file_path'
    ]
    # 构建 INSERT OR REPLACE 语句
    placeholders = ', '.join(['?'] * len(fields))
    columns = ', '.join(fields)
    values = []
    for f in fields:
        val = data.get(f)
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        elif isinstance(val, bool):
            val = 1 if val else 0
        values.append(val)

    conn.execute(
        f"INSERT OR REPLACE INTO resumes ({columns}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    conn.close()


def get_resumes(status_filter='', search='', degree='', direction=''):
    """查询简历库，支持筛选和搜索。

    SQL WHERE 子句是动态拼接的——用户选了哪些筛选项，就加上对应的条件。
    """
    conn = get_conn()
    sql = "SELECT * FROM resumes WHERE 1=1"  # 1=1 是占位符，方便后面拼 AND 条件
    params = []

    if status_filter:
        sql += " AND interview_status = ?"
        params.append(status_filter)
    if degree:
        sql += " AND degree = ?"
        params.append(degree)
    if direction:
        sql += " AND tech_direction = ?"
        params.append(direction)
    if search:
        # LIKE 是模糊匹配，% 是通配符，表示"任意字符"
        sql += " AND (name LIKE ? OR school LIKE ? OR current_company LIKE ? OR skills LIKE ? OR resume_text LIKE ?)"
        kw = f"%{search}%"
        params.extend([kw, kw, kw, kw, kw])

    sql += " ORDER BY created_at DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def update_status(id_val, status):
    """更新面试状态。"""
    conn = get_conn()
    conn.execute(
        "UPDATE resumes SET interview_status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id_val),
    )
    conn.commit()
    conn.close()


def delete_resume(id_val):
    """删除简历。"""
    conn = get_conn()
    conn.execute("DELETE FROM resumes WHERE id = ?", (id_val,))
    conn.commit()
    conn.close()


# =============================================================================
# 数据分析查询
# =============================================================================

def get_analytics_data():
    """供可视化页面使用的聚合查询。

    返回三个 DataFrame，分别给漏斗图、人才画像、来源分析用。
    全部从 resumes 表查——因为旧系统的 23 个字段适合做分析。
    """
    conn = get_conn()

    # ── 漏斗数据：各阶段的人数，按 pipeline_stages.sort_order 排列 ──
    # 漏斗 = 累积计数：每个阶段的人数 = 该阶段及之后所有阶段的人数总和
    # 逻辑：到达"一面"的人必然经过了"筛选"和"评估"
    funnel_df = pd.read_sql_query("""
        SELECT s.name,
               (SELECT COUNT(*)
                FROM resumes r
                INNER JOIN pipeline_stages s2 ON r.interview_status = s2.name
                WHERE s2.sort_order >= s.sort_order) as count
        FROM pipeline_stages s
        ORDER BY s.sort_order
    """, conn)

    # ── 人才画像：学历分布、技能、年限等 ──
    degree_df = pd.read_sql_query("""
        SELECT degree, COUNT(*) as count
        FROM resumes
        WHERE degree IS NOT NULL AND degree != ''
        GROUP BY degree
        ORDER BY count DESC
    """, conn)

    direction_df = pd.read_sql_query("""
        SELECT tech_direction, COUNT(*) as count
        FROM resumes
        WHERE tech_direction IS NOT NULL AND tech_direction != ''
        GROUP BY tech_direction
        ORDER BY count DESC
    """, conn)

    # ── 来源分析：渠道、学校、公司 ──
    source_df = pd.read_sql_query("""
        SELECT source, COUNT(*) as count
        FROM resumes
        WHERE source IS NOT NULL AND source != ''
        GROUP BY source
        ORDER BY count DESC
    """, conn)

    school_df = pd.read_sql_query("""
        SELECT school, COUNT(*) as count
        FROM resumes
        WHERE school IS NOT NULL AND school != ''
        GROUP BY school
        ORDER BY count DESC
        LIMIT 10
    """, conn)

    company_df = pd.read_sql_query("""
        SELECT current_company, COUNT(*) as count
        FROM resumes
        WHERE current_company IS NOT NULL AND current_company != ''
        GROUP BY current_company
        ORDER BY count DESC
        LIMIT 10
    """, conn)

    conn.close()
    return {
        "funnel": funnel_df,
        "degree": degree_df,
        "direction": direction_df,
        "source": source_df,
        "school": school_df,
        "company": company_df,
    }


# =============================================================================
# 旧数据迁移
# =============================================================================

def migrate_legacy_data(json_path):
    """把旧系统的 示例简历.json 导入到 SQLite 的 resumes 表。

    用 INSERT OR IGNORE：遇到重复 unique_code 就跳过。
    """
    import os
    if not os.path.exists(json_path):
        print(f"文件不存在: {json_path}")
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("JSON 格式错误：需要数组")
        return 0

    conn = get_conn()
    count = 0
    for r in data:
        # 把 JSON 中的字段映射到数据库列
        try:
            conn.execute("""
                INSERT OR IGNORE INTO resumes (
                    unique_code, name, gender, age, phone, email, city,
                    school, degree, major, graduation_year,
                    current_company, current_position,
                    work_years, employment_status,
                    current_salary, expected_salary,
                    skills, tech_direction, source,
                    target_position, interview_status,
                    hr_notes, resume_text, has_top_papers,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('unique_code', ''),
                r.get('name', ''),
                r.get('gender', ''),
                r.get('age', ''),
                r.get('phone', ''),
                r.get('email', ''),
                r.get('city', ''),
                r.get('school', ''),
                r.get('degree', ''),
                r.get('major', ''),
                r.get('graduation_year', ''),
                r.get('current_company', ''),
                r.get('current_position', ''),
                r.get('work_years', ''),
                r.get('employment_status', ''),
                r.get('current_salary', ''),
                r.get('expected_salary', ''),
                json.dumps(r.get('skills', []), ensure_ascii=False),
                r.get('tech_direction', ''),
                r.get('source', ''),
                r.get('target_position', ''),
                r.get('interview_status', '筛选'),
                r.get('hr_notes', ''),
                r.get('resume_text', ''),
                1 if r.get('has_top_papers') else 0,
                r.get('created_at', datetime.now().isoformat()),
                r.get('updated_at', datetime.now().isoformat()),
            ))
            count += 1
        except Exception as e:
            print(f"跳过 {r.get('name', '?')}: {e}")

    conn.commit()
    conn.close()
    print(f"迁移完成：{count} 条记录")
    return count


# =============================================================================
# 启动时自动执行
# =============================================================================
if __name__ == "__main__":
    import os
    init_db()
    print("[OK] 数据库初始化完成")

    # 尝试迁移旧数据
    legacy_file = "示例简历.json"
    if os.path.exists(legacy_file):
        n = migrate_legacy_data(legacy_file)
        print(f"[OK] 已迁移 {n} 条旧简历数据")
    else:
        print("[INFO] 未找到旧数据文件，跳过迁移")
