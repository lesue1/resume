"""
keyword_matcher.py — 免费快速筛选引擎
======================================
零 API 调用，纯关键词字典匹配。用于批量评估的"第一阶段"：
快速筛掉明显不匹配的简历，剩下再调 AI 精评。

用法:
    from keyword_matcher import quick_match
    result = quick_match(jd_text, resume_text)
    # → {"match_pct": 75.0, "matched": [...], "missed": [...], "total": 12}
"""

import re

# ═══════════════════════════════════════════════════════════
# 技术关键词字典 (~350 个，中英混合)
# ═══════════════════════════════════════════════════════════

TECH_KEYWORDS = {
    # ── 编程语言 ──
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "Rust",
    "C++", "CPP", "C#", "CSharp", "Ruby", "PHP", "Swift", "Kotlin",
    "Scala", "R", "MATLAB", "Perl", "Lua", "Dart", "Shell", "Bash",
    "SQL", "HTML", "HTML5", "CSS", "CSS3", "Sass", "SCSS", "Less",
    "Objective-C", "Groovy",

    # ── Python 框架 ──
    "Flask", "Django", "FastAPI", "Tornado", "Sanic", "Falcon",
    "aiohttp", "Celery", "SQLAlchemy", "Alembic", "Pydantic",
    "Gunicorn", "uWSGI", "uvicorn",

    # ── 前端框架/库 ──
    "React", "Vue", "Vue.js", "Angular", "Svelte", "Next.js", "Nuxt",
    "Gatsby", "jQuery", "Bootstrap", "Tailwind", "Tailwind CSS",
    "Element UI", "Ant Design", "Material UI", "Redux", "Zustand",
    "Pinia", "Vuex", "Webpack", "Vite", "Rollup", "esbuild",
    "Babel", "ESLint", "Prettier",

    # ── 后端框架 ──
    "Spring Boot", "Spring", "Express", "NestJS", "Koa", "Laravel",
    "Ruby on Rails", "ASP.NET", ".NET", "Node.js", "Deno",
    "GraphQL", "gRPC", "REST", "RESTful", "WebSocket", "SOAP",

    # ── 数据库/存储 ──
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "SQLite", "Oracle", "SQL Server", "MariaDB", "Cassandra",
    "DynamoDB", "BigQuery", "HBase", "Neo4j", "ClickHouse",
    "TiDB", "Snowflake", "MinIO", "Ceph", "HDFS",

    # ── 消息队列/流处理 ──
    "Kafka", "RabbitMQ", "RocketMQ", "Pulsar", "NATS", "Redis Streams",
    "Flink", "Spark Streaming", "Storm", "ActiveMQ",

    # ── 云平台/基础设施 ──
    "AWS", "GCP", "Azure", "阿里云", "腾讯云", "华为云",
    "Docker", "Kubernetes", "K8s", "Terraform", "Ansible",
    "Pulumi", "Helm", "Istio", "Envoy", "Consul", "Etcd",
    "Prometheus", "Grafana", "Jaeger", "ELK", "Loki",
    "Nginx", "Apache", "Caddy", "HAProxy",
    "Jenkins", "GitHub Actions", "GitLab CI", "CircleCI",
    "ArgoCD", "Spinnaker", "Travis CI", "Bamboo",

    # ── AI/ML/数据科学 ──
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "机器学习", "深度学习", "自然语言处理", "计算机视觉",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost",
    "LightGBM", "CatBoost", "JAX", "MXNet", "Caffe",
    "Pandas", "NumPy", "SciPy", "Matplotlib", "Seaborn", "Plotly",
    "Hugging Face", "Transformers", "LangChain", "LlamaIndex",
    "RAG", "Agent", "Prompt Engineering", "Fine-tuning",
    "LLM", "大模型", "预训练", "SFT", "RLHF",
    "CUDA", "cuDNN", "TensorRT", "ONNX", "OpenVINO",
    "Spark MLlib", "MLflow", "Kubeflow", "Airflow",
    "Jupyter", "Tableau", "PowerBI", "Metabase", "Superset",

    # ── 微服务/架构 ──
    "微服务", "分布式", "高并发", "高可用", "服务治理",
    "DDD", "领域驱动", "Event Driven", "CQRS", "Saga",
    "Service Mesh", "API Gateway", "负载均衡", "熔断", "限流",

    # ── 移动端 ──
    "Android", "iOS", "React Native", "Flutter", "SwiftUI",
    "Xcode", "Gradle", "Kotlin Multiplatform", "Jetpack Compose",

    # ── 测试 ──
    "pytest", "unittest", "JUnit", "Selenium", "Cypress",
    "Playwright", "Jest", "Mocha", "TestNG", "Appium",
    "单元测试", "集成测试", "E2E", "性能测试", "压测",

    # ── 版本控制/协作 ──
    "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
    "Code Review", "CI/CD", "DevOps", "DevSecOps", "Agile",

    # ── 安全 ──
    "OAuth", "OAuth2", "JWT", "SAML", "OpenID Connect",
    "SQL注入", "XSS", "CSRF", "SSRF", "OWASP",
    "HTTPS", "SSL", "TLS", "WAF", "零信任",

    # ── 操作系统 ──
    "Linux", "Unix", "CentOS", "Ubuntu", "Debian", "Red Hat",
    "Windows Server", "macOS", "Shell脚本",

    # ── 通用能力词 ──
    "敏捷", "Scrum", "Kanban", "技术方案", "架构设计",
    "性能优化", "系统设计", "项目管理", "技术选型",
    "数据仓库", "数据湖", "ETL", "数据治理", "数据建模",
    "A/B测试", "AB测试", "用户画像", "漏斗分析", "留存分析",

    # ── HR 数据方向特有 ──
    "招聘", "绩效", "薪酬", "人才盘点", "组织诊断",
    "HRIS", "人力资源信息系统", "People Analytics",
    "离职预测", "胜任力模型", "HC", "Headcount",

    # ── 软技能（也出现在 JD 里）──
    "沟通", "协调", "跨团队", "Owner", "自驱", "owner意识",
    "英语", "CET-6", "雅思", "托福",
}

# ── 教育背景关键词（学历匹配）──
EDUCATION_KEYWORDS = {
    "博士", "硕士", "本科", "大专", "MBA", "EMBA",
    "985", "211", "双一流", "一本",
    "计算机科学", "软件工程", "人工智能", "数据科学",
    "统计学", "数学", "信息管理", "电子信息",
    "通信工程", "自动化", "电子工程", "网络工程",
}

# ── 经验年限模式（正则匹配）──
YEAR_PATTERNS = [
    re.compile(r'(\d+)[\s\-~至到]*年'),           # "3年" "3-5年"
    re.compile(r'(\d+)\s*years?', re.IGNORECASE),  # "3 years"
    re.compile(r'(?:熟悉|精通|了解).*?(\d+)\s*年'),  # "熟悉XXX 3年以上"
]


# ═══════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════

def _normalize(text):
    """统一小写 + 合并空白，方便匹配。"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _extract_jd_keywords(jd_text):
    """从 JD 文本中提取匹配到的技术关键词。

    返回 (matched_keywords, all_found_terms) 两个列表。
    all_found_terms 包含词典中 AND 正则模式匹配到的所有术语。
    """
    norm = _normalize(jd_text)
    found = []

    for kw in TECH_KEYWORDS:
        kw_norm = _normalize(kw)
        if not kw_norm:
            continue
        # 多词术语用子串匹配（含空格或中文）
        if ' ' in kw_norm or any('一' <= c <= '鿿' for c in kw_norm):
            if kw_norm in norm:
                found.append(kw)
        else:
            # 单英文词用词边界匹配，防误伤（如 "Go" 不匹配 "Google"）
            pattern = r'(?<![a-zA-Z])' + re.escape(kw_norm) + r'(?![a-zA-Z])'
            if re.search(pattern, norm):
                found.append(kw)

    # 去重并保留原始大小写
    seen = set()
    unique = []
    for kw in found:
        if _normalize(kw) not in seen:
            seen.add(_normalize(kw))
            unique.append(kw)

    return unique


def quick_match(jd_text, resume_text):
    """单份简历 vs JD 的快速关键词匹配。

    参数:
        jd_text: 岗位描述文本
        resume_text: 简历文本

    返回:
        {
            "match_pct": 75.0,          # 百分比 0-100
            "matched": ["Python","Flask"],  # 命中的关键词
            "missed": ["Docker","K8s"],     # JD有但简历没有的关键词
            "total": 12,                    # JD 中识别到的关键词总数
        }
    """
    if not jd_text or not resume_text:
        return {"match_pct": 0, "matched": [], "missed": [], "total": 0}

    jd_keywords = _extract_jd_keywords(jd_text)
    if not jd_keywords:
        return {"match_pct": 100.0, "matched": [], "missed": [], "total": 0}

    norm_resume = _normalize(resume_text)
    matched = []
    missed = []

    for kw in jd_keywords:
        kw_norm = _normalize(kw)
        if ' ' in kw_norm or any('一' <= c <= '鿿' for c in kw_norm):
            hit = kw_norm in norm_resume
        else:
            pattern = r'(?<![a-zA-Z])' + re.escape(kw_norm) + r'(?![a-zA-Z])'
            hit = bool(re.search(pattern, norm_resume))
        if hit:
            matched.append(kw)
        else:
            missed.append(kw)

    total = len(jd_keywords)
    match_pct = round(len(matched) / total * 100, 1) if total > 0 else 100.0

    return {
        "match_pct": match_pct,
        "matched": matched,
        "missed": missed,
        "total": total,
    }


def quick_match_batch(jd_text, resumes):
    """批量快速筛选——一份 JD 对多份简历。

    参数:
        jd_text: 岗位描述
        resumes: [{"name": "张三", "text": "简历内容..."}, ...]

    返回:
        [{"name": "张三", "match_pct": 85.0, "matched": [...], "missed": [...], "total": 12}, ...]
        按 match_pct 降序排列。
    """
    results = []
    for r in resumes:
        name = r.get("name", "未知")
        text = r.get("text", "")
        match = quick_match(jd_text, text)
        match["name"] = name
        results.append(match)

    results.sort(key=lambda x: x["match_pct"], reverse=True)
    return results


# ═══════════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    test_jd = """
    岗位：Python 后端开发工程师
    要求：精通 Python、Flask/Django，熟悉 MySQL/PostgreSQL，
          了解 Docker、Linux，2年以上后端开发经验，
          有 AI/ML 项目经验优先。
    """

    test_resumes = [
        ("张三 (匹配)", """
        张三 | Python 开发工程师 3年经验
        技能：Python, Flask, Django, MySQL, PostgreSQL, Docker, Linux
        项目：用 Flask 开发了内部管理系统，Docker 部署，MySQL 优化
        """),
        ("李四 (部分)", """
        李四 | Java 开发 5年
        技能：Java, Spring Boot, Oracle, Docker
        自学过 Python 但没用在工作里
        """),
        ("王五 (不匹配)", """
        王五 | 销售经理 8年
        技能：销售管理，客户关系，Excel
        没有任何编程经验
        """),
    ]

    print("=" * 55)
    print("关键词匹配自测")
    print("=" * 55)

    for name, resume in test_resumes:
        result = quick_match(test_jd, resume)
        bar = "#" * int(result["match_pct"] / 10) + "-" * (10 - int(result["match_pct"] / 10))
        print(f"\n{name}")
        print(f"  命中率: {bar} {result['match_pct']}% ({len(result['matched'])}/{result['total']})")
        if result["matched"]:
            print(f"  [OK] 命中: {', '.join(result['matched'][:8])}")
        if result["missed"]:
            print(f"  [--] 遗漏: {', '.join(result['missed'][:8])}")

    print("\n" + "=" * 55)
    print("批量模式测试:")
    batch_input = [{"name": n, "text": t} for n, t in test_resumes]
    batch_result = quick_match_batch(test_jd, batch_input)
    for r in batch_result:
        print(f"  {r['name']}: {r['match_pct']}%")
