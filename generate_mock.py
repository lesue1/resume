"""
generate_mock.py — 生成高质量演示数据
======================================
生成岗位 JD + 段落式简历 + 预评分，让系统打开就有完整演示内容。
"""

import sqlite3
import os
import json
import sys

DB = os.path.join(os.path.dirname(__file__), 'resume_screening.db')

# ============================================================
# 岗位 JD（5个，涵盖不同技术方向）
# ============================================================
JOBS = [
    {
        "title": "AI算法工程师（大模型方向）",
        "department": "AI研究院",
        "requirements": "硕士及以上，3年+ NLP/CV 经验，有大模型预训练/微调经验优先",
        "jd_text": """【岗位职责】
1. 负责大语言模型（LLM）的预训练、SFT、RLHF 全流程研发
2. 探索 MoE 架构、Long Context、多模态等前沿方向
3. 搭建模型评估体系，包括自动化评测和人工评测
4. 将大模型能力落地到具体业务场景（智能客服、代码生成、文档理解）

【任职要求】
- 精通 PyTorch/Transformers，熟悉 DeepSpeed/Megatron 等分布式训练框架
- 有百亿级以上参数模型训练经验，熟悉 GPU 集群调度
- 扎实的算法基础，在 ACL/EMNLP/NeurIPS 等顶会发表过论文优先
- 良好的工程能力，能独立完成数据处理→训练→部署的全链路"""
    },
    {
        "title": "Python后端开发工程师",
        "department": "基础架构部",
        "requirements": "本科及以上，熟悉 Python/Go，有分布式系统经验者优先",
        "jd_text": """【岗位职责】
1. 负责公司核心业务系统的后端架构设计与开发
2. 参与微服务治理，包括服务发现、限流熔断、链路追踪
3. 优化数据库性能，解决高并发场景下的数据一致性问题
4. 编写技术方案文档，参与 Code Review

【任职要求】
- 精通 Python（Django/Flask/FastAPI 至少一种），或 Go/Java 并愿意转 Python
- 熟悉 MySQL/PostgreSQL 索引优化和分库分表策略
- 熟悉 Redis/Kafka 等中间件的使用场景
- 有 Docker/K8s 生产环境经验，理解 CI/CD 流程
- 加分项：有开源贡献或技术博客"""
    },
    {
        "title": "数据分析师（HR方向）",
        "department": "人力资源部",
        "requirements": "本科及以上，熟练使用 SQL/Python，有 HR 领域数据分析经验优先",
        "jd_text": """【岗位职责】
1. 搭建 HR 数据指标体系，涵盖招聘、绩效、离职、薪酬等核心模块
2. 通过数据分析驱动人才决策——识别高离职风险部门、优化招聘渠道效率
3. 开发 HR 数据看板（BI 报表），让管理层实时掌握人力健康度
4. 探索 AI 在 HR 场景的应用：简历智能筛选、员工流失预测、人岗匹配模型

【任职要求】
- 精通 SQL，能独立完成复杂多表查询和数据清洗
- 熟练使用 Python（Pandas/Matplotlib）进行数据分析和可视化
- 有 Tableau/PowerBI/Metabase 等 BI 工具使用经验
- 对 HR 领域有好奇心，理解招聘、绩效、培训等基本业务流程
- 加分项：有数据分析驱动业务决策的实际案例"""
    },
    {
        "title": "前端开发工程师",
        "department": "产品研发部",
        "requirements": "本科及以上，3年+ 前端经验，精通 React 或 Vue",
        "jd_text": """【岗位职责】
1. 负责公司核心产品的前端架构设计与页面开发
2. 参与组件库搭建，推动前端工程化建设
3. 优化页面性能和加载速度（LCP/FID 等核心指标）
4. 与设计师和后端紧密协作，将产品需求高质量落地

【任职要求】
- 精通 React/Vue 至少一种，有 TypeScript 大型项目经验
- 熟悉前端工程化（Webpack/Vite、Monorepo、CI/CD）
- 有性能优化实战经验，能说清关键指标的提升路径
- 了解 Node.js，有 BFF 层或 SSR 经验优先
- 加分项：有开源组件库或技术博客"""
    },
    {
        "title": "产品经理（AI应用方向）",
        "department": "AI产品部",
        "requirements": "本科及以上，2年+ 产品经验，对 AI 技术有理解",
        "jd_text": """【岗位职责】
1. 负责 AI 产品的需求分析、功能设计和迭代规划
2. 深度理解用户场景，将 AI 能力转化为产品功能
3. 追踪行业动态和竞品，输出产品路线图
4. 协调算法、工程、设计多方资源，推动产品落地

【任职要求】
- 有从 0 到 1 的产品经验，能独立完成 PRD 和原型设计
- 对 AI/ML 技术有基本理解，知道什么场景适合用模型解决
- 数据驱动，能通过 A/B 测试和用户数据指导迭代
- 极强的沟通能力和执行力，能推动跨团队协作
- 加分项：有 AI 产品经验（ChatBot、推荐系统、搜索等）"""
    },
]


# ============================================================
# 模拟候选人简历（20份，段落式，质量分档）
# ============================================================

CANDIDATES = [
    # ═══════ 顶尖档：85-95分预期 ═══════ (4人)
    {
        "name": "张明远", "gender": "男", "age": "28", "phone": "13800001001",
        "email": "zhangmy@qq.com", "city": "北京",
        "school": "清华大学", "degree": "硕士", "major": "计算机科学与技术",
        "graduation_year": "2023", "current_company": "字节跳动",
        "current_position": "算法工程师", "work_years": "3年",
        "employment_status": "在职",
        "current_salary": "55K", "expected_salary": "70K",
        "skills": "PyTorch, Transformers, DeepSpeed, Megatron-LM, CUDA, vLLM, 大模型预训练",
        "tech_direction": "算法", "source": "内推",
        "target_position": "AI算法工程师（大模型方向）",
        "interview_status": "评估", "has_top_papers": 1,
        "resume_text": """张明远 | 男 | 28岁 | 13800001001 | zhangmy@qq.com | 北京

教育背景
2019-2023 清华大学 计算机科学与技术 硕士（保研，导师李沐团队）
2015-2019 电子科技大学 计算机科学与技术 本科（GPA 3.9/4.0，专业前5%）

工作经历
2023.07-至今 字节跳动 AI Lab | 算法工程师
- 参与千亿参数大模型的预训练工作，负责数据清洗 pipeline 搭建和分布式训练优化
- 搭建基于 Megatron-LM + DeepSpeed 的分布式训练框架，128 卡 A100 集群训练效率提升 23%
- 主导模型评估体系建设：设计自动化评测集 3000+ 题，覆盖推理、代码、对话等 8 个维度
- 开源项目贡献：给 vLLM 提了 3 个 PR（1 个已合并，关于 KV Cache 内存优化）
- 在 ACL 2024 发表论文一篇（一作）：《Efficient Long-Context Training via Hierarchical Attention》

项目经历
• MiniMind 轻量大模型复现项目（个人）：从 0 用 PyTorch 写了一个 0.2B 参数的 GPT，训练代码 + 数据 + 部署全开源，GitHub 2300+ star
• 公司内部 RAG 系统：基于 LangChain 搭建文档问答系统，支持 10 万+ 文档检索，端到端延迟从 8s 降到 2.1s

技能
PyTorch（精通）、Transformers（精通）、DeepSpeed（熟练）、CUDA 编程（熟练）、vLLM（持续贡献）、大模型全流程"""
    },
    {
        "name": "陈思雨", "gender": "女", "age": "26", "phone": "13900002002",
        "email": "chensy@gmail.com", "city": "深圳",
        "school": "北京大学", "degree": "硕士", "major": "人工智能",
        "graduation_year": "2024", "current_company": "腾讯",
        "current_position": "NLP工程师", "work_years": "2年",
        "employment_status": "在职",
        "current_salary": "45K", "expected_salary": "55K",
        "skills": "PyTorch, HuggingFace, LangChain, RAG, Agent, Prompt Engineering, 大模型应用",
        "tech_direction": "算法", "source": "校招",
        "target_position": "AI算法工程师（大模型方向）",
        "interview_status": "一面", "has_top_papers": 1,
        "resume_text": """陈思雨 | 女 | 26岁 | 13900002002 | chensy@gmail.com | 深圳

教育背景
2021-2024 北京大学 人工智能 硕士（研究方向：自然语言处理）
2017-2021 南京大学 计算机科学与技术 本科（GPA 4.45/5.0）

工作经历
2024.03-至今 腾讯 CSIG | NLP工程师
- 负责腾讯云大模型产品的应用层开发，将混元大模型落地到客服、知识库等场景
- 设计 Agent 框架：支持工具调用 + 多轮规划 + 记忆管理，在客服场景下问题解决率从 62% 提升到 81%
- 搭建 RAG Pipeline：基于 Elasticsearch + 向量数据库，检索准确率 92%，召回率 88%
- 产出内部技术文档 30+ 篇，带 2 名实习生

实习经历
2023.06-2023.12 微软亚洲研究院 | 研究实习生
- 研究大模型幻觉问题，提出基于检索增强的幻觉检测方法，在 TruthfulQA 上提升 11%

项目经历
• ChatYourData（开源）：支持用户上传数据构建私有知识库问答系统，GitHub 800+ star
• 参加 2023 百度千帆大模型比赛获二等奖

技能
PyTorch（熟练）、Transformers（熟练）、LangChain（精通）、RAG/Agent（精通）、Prompt Engineering（精通）"""
    },
    {
        "name": "王浩然", "gender": "男", "age": "30", "phone": "13700003003",
        "email": "wanghr@163.com", "city": "杭州",
        "school": "浙江大学", "degree": "博士", "major": "计算机科学与技术",
        "graduation_year": "2021", "current_company": "阿里巴巴",
        "current_position": "高级算法专家", "work_years": "5年",
        "employment_status": "在职",
        "current_salary": "80K", "expected_salary": "100K",
        "skills": "PyTorch, TensorFlow, 大模型, 推荐系统, 图神经网络, Spark, Flink",
        "tech_direction": "算法", "source": "猎头",
        "target_position": "AI算法工程师（大模型方向）",
        "interview_status": "二面", "has_top_papers": 1,
        "resume_text": """王浩然 | 男 | 30岁 | 13700003003 | wanghr@163.com | 杭州

教育背景
2016-2021 浙江大学 计算机科学与技术 博士（导师：吴飞教授，研究方向：推荐系统与图神经网络）
2012-2016 华中科技大学 软件工程 本科（GPA 3.7/4.0）

工作经历
2021.07-至今 阿里巴巴 淘宝事业部 | 高级算法专家
- 负责淘宝首页推荐系统的算法迭代，服务 5 亿+ DAU，点击率提升 18%，GMV 增长贡献 9%
- 主导从传统协同过滤到深度学习推荐模型的升级，模型规模从 1000 万参数扩展到 10 亿参数
- 搭建实时特征平台，特征更新延迟从小时级降到分钟级，支撑在线推理 QPS 100 万+
- 带 5 人算法团队，制定技术路线、分配任务、做 Code Review

2023.06-至今（兼） 阿里通义大模型团队 | 核心贡献者
- 参与大模型推荐场景的应用探索：用 LLM 做用户意图理解和商品知识图谱构建
- 设计基于大模型的冷启动策略，新用户首日转化率提升 22%

论文与影响力
- NeurIPS/ICML/KDD 发表论文 6 篇（其中 3 篇一作），Google Scholar 引用 1200+
- 国家发明专利 4 项（已授权 2 项）
- 曾获阿里巴巴"技术之星"（同级别前 5%）

技能
PyTorch/TensorFlow（精通）、大模型应用（熟练）、推荐系统（精通）、Spark/Flink（熟练）、分布式训练"""
    },
    {
        "name": "赵晨阳", "gender": "女", "age": "27", "phone": "13600004004",
        "email": "zhaocy@qq.com", "city": "北京",
        "school": "上海交通大学", "degree": "硕士", "major": "软件工程",
        "graduation_year": "2022", "current_company": "快手",
        "current_position": "Python后端工程师", "work_years": "3年",
        "employment_status": "在职",
        "current_salary": "35K", "expected_salary": "45K",
        "skills": "Python, Go, Flask, FastAPI, MySQL, PostgreSQL, Redis, Kafka, Docker, K8s, 微服务, 分布式系统",
        "tech_direction": "后端", "source": "Boss直聘",
        "target_position": "Python后端开发工程师",
        "interview_status": "评估", "has_top_papers": 0,
        "resume_text": """赵晨阳 | 女 | 27岁 | 13600004004 | zhaocy@qq.com | 北京

教育背景
2019-2022 上海交通大学 软件工程 硕士
2015-2019 四川大学 软件工程 本科

工作经历
2022.04-至今 快手 基础架构部 | Python后端工程师
- 负责快手内部 CI/CD 平台的开发，日均构建 5000+ 次，服务 2000+ 开发者
- 主导平台从 Flask 单体架构到 FastAPI 微服务架构的拆解，接口平均响应时间从 340ms 降到 80ms
- 设计分布式任务调度系统：基于 Redis + Celery，支持 1000+ 并发任务，任务积压率 < 0.5%
- MySQL 慢查询优化：将 Top 20 慢 SQL 的执行时间平均降低 75%（从 8s → 2s），主要是索引优化和 SQL 重写
- 写了公司内部 PostgreSQL 最佳实践文档，被 3 个兄弟团队采纳

2021.06-2021.12 字节跳动（实习） 架构部 | 后端开发实习生
- 参与抖音内部运营平台的开发，独立负责活动配置模块（从需求到上线）

项目经历
• mini-scheduler（开源）：用 Python 实现的一个轻量级分布式任务调度器，GitHub 500+ star
• 技术博客（zhuanlan.zhihu.com）：写后端技术文章，累计阅读 50 万+，粉丝 8000+

技能
Python（精通）、Go（熟练）、Flask/FastAPI（精通）、MySQL/PostgreSQL（精通）、Redis/Kafka（熟练）、Docker/K8s（熟练）、微服务架构（熟练）"""
    },

    # ═══════ 合格档：65-84分预期 ═══════ (8人)
    {
        "name": "刘子轩", "gender": "男", "age": "25", "phone": "13500005005",
        "email": "liuzx@126.com", "city": "上海",
        "school": "华中科技大学", "degree": "本科", "major": "计算机科学与技术",
        "graduation_year": "2023", "current_company": "Thoughtworks",
        "current_position": "后端开发工程师", "work_years": "2年",
        "employment_status": "在职",
        "current_salary": "22K", "expected_salary": "30K",
        "skills": "Python, Django, MySQL, Redis, Docker, Git, AWS",
        "tech_direction": "后端", "source": "拉勾",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """刘子轩 | 男 | 25岁 | 13500005005 | liuzx@126.com | 上海

教育背景
2019-2023 华中科技大学 计算机科学与技术 本科（GPA 3.2/4.0）

工作经历
2023.07-至今 Thoughtworks 中国 | 后端开发工程师
- 为客户（某外资银行）开发内部风控系统，使用 Django + PostgreSQL 技术栈
- 独立负责交易异常检测模块：从需求分析→数据库设计→API 开发→上线，每天处理 50 万+ 条交易记录
- 引入 Redis 缓存热点风控规则，查询耗时从 120ms 降到 15ms
- 编写单元测试覆盖率从 35% 提升到 72%

2022.07-2022.12 武汉某创业公司 | Python 实习
- 用 Flask 开发公司内部 CRM 系统，管理 500+ 客户数据

项目经历
• 毕业设计：基于机器学习的学生成绩预测系统（Python + Scikit-learn + Flask），准确率 82%
• 在学校 ACM 实验室干过一年，参加过 3 次区域赛（最好成绩银牌）

技能
Python（熟练）、Django（熟练）、MySQL（熟练）、Redis（了解）、Docker（了解）、AWS（了解）"""
    },
    {
        "name": "林佳慧", "gender": "女", "age": "24", "phone": "13400006006",
        "email": "linjh@qq.com", "city": "广州",
        "school": "中山大学", "degree": "本科", "major": "统计学",
        "graduation_year": "2024", "current_company": "SHEIN",
        "current_position": "数据分析师", "work_years": "应届",
        "employment_status": "离职",
        "current_salary": "15K", "expected_salary": "20K",
        "skills": "SQL, Python, Pandas, Matplotlib, Tableau, Excel, 数据分析, A/B测试",
        "tech_direction": "数据", "source": "官网投递",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """林佳慧 | 女 | 24岁 | 13400006006 | linjh@qq.com | 广州

教育背景
2020-2024 中山大学 统计学 本科（GPA 3.6/4.0，专业前 20%）

实习经历
2023.07-2023.12 SHEIN 数据部 | 数据分析实习生
- 负责电商用户行为分析：用 SQL 从数仓取数，分析用户留存、转化漏斗等核心指标
- 搭建异常订单监控看板（Tableau），覆盖 6 个业务指标，异常检测准确率从 70% 提升到 89%
- 协助 A/B 测试的数据分析：对比实验组和对照组在 CTR/CVR 等指标上的差异，输出分析报告 8 个

项目经历
• 招聘渠道效率分析项目（个人项目）：爬取某招聘网站数据，用 Python 分析各渠道的简历转化率、人均成本、到面率，发现内推渠道的 ROI 是猎头的 3 倍
• 校园比赛：全国大学生数学建模竞赛省一等奖

技能
SQL（精通——复杂多表 JOIN、窗口函数、子查询）、Python Pandas（熟练）、Tableau（熟练）、Excel（精通）、A/B 测试（了解）"""
    },
    {
        "name": "黄奕辰", "gender": "男", "age": "29", "phone": "13300007007",
        "email": "huangyc@gmail.com", "city": "成都",
        "school": "电子科技大学", "degree": "本科", "major": "通信工程",
        "graduation_year": "2019", "current_company": "华为",
        "current_position": "C++开发工程师", "work_years": "6年",
        "employment_status": "在职",
        "current_salary": "40K", "expected_salary": "50K",
        "skills": "C++, Python, Linux, TCP/IP, 嵌入式, RTOS, STM32",
        "tech_direction": "后端", "source": "脉脉",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """黄奕辰 | 男 | 29岁 | 13300007007 | huangyc@gmail.com | 成都

教育背景
2015-2019 电子科技大学 通信工程 本科

工作经历
2019.07-至今 华为 成都研究所 | C++开发工程师
- 负责 5G 基站协议栈软件的开发和维护，代码量 30 万+ 行
- 主导某模块的性能优化：通过算法改进 + 内存池管理，处理时延从 12ms 降到 4ms
- 参与 3 次大版本升级，每次独立负责 1-2 个子模块的设计和开发
- 带过 2 个新人，制定 Onboarding 计划

技能与转行说明
- C/C++ 精通（6 年经验），Python 自学的（写过自动化测试脚本和数据处理工具，约 1 年）
- 想从通信转互联网后端，正在系统学习：已学完《Fluent Python》和《Designing Data-Intensive Applications》
- 有 Linux 内核调试经验，对底层比较熟——这应该能帮助理解分布式系统的底层原理
- 目前在做一个用 Python/FastAPI 写的博客系统练手"""
    },
    {
        "name": "杨若溪", "gender": "女", "age": "26", "phone": "13200008008",
        "email": "yangrx@163.com", "city": "北京",
        "school": "北京邮电大学", "degree": "硕士", "major": "管理科学与工程",
        "graduation_year": "2024", "current_company": "美团",
        "current_position": "HR数据分析实习生", "work_years": "应届",
        "employment_status": "实习",
        "current_salary": "10K", "expected_salary": "18K",
        "skills": "SQL, Python, Tableau, Excel, 人力资源信息系统, 数据分析, PowerBI",
        "tech_direction": "数据", "source": "校招",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "评估", "has_top_papers": 0,
        "resume_text": """杨若溪 | 女 | 26岁 | 13200008008 | yangrx@163.com | 北京

教育背景
2021-2024 北京邮电大学 管理科学与工程 硕士（研究方向：人力资源管理）
2017-2021 郑州大学 人力资源管理 本科（GPA 3.5/4.0）

实习经历
2023.09-至今 美团 HR COE团队 | HR数据分析实习生
- 搭建招聘数据看板（Tableau）：跟踪各 BU 的招聘进度、Offer 接受率、招聘周期等指标
- 分析离职数据：用 Python 跑逻辑回归，发现"入职后第一个月加班时长"是离职的最强预测因子（OR=2.3）
- 协助设计 A/B 测试：新面试流程（在 2 个 BU 试跑）对应聘者体验的影响，输出分析报告供 VP 决策
- 推动建立 HR 数据指标体系：从原来只有"招了多少人"，扩展到 15 个核心指标

2023.03-2023.06 某创业公司 | 数据分析实习生
- 用 SQL + Python 分析用户增长数据，发现某渠道 ROI 极低，建议停投后被采纳

项目经历
• 硕士论文：《基于机器学习的员工离职预测模型研究》，对比了逻辑回归、随机森林、XGBoost，最优模型 AUC=0.86
• 自学 Python 两年，在 Coursera 上完成了《Machine Learning》（Andrew Ng）和《Data Science》专项课

技能
SQL（熟练）、Python（Pandas/Scikit-learn，熟练）、Tableau（熟练）、PowerBI（了解）、Excel（精通）"""
    },
    {
        "name": "周天宇", "gender": "男", "age": "27", "phone": "13100009009",
        "email": "zhouty@qq.com", "city": "深圳",
        "school": "深圳大学", "degree": "本科", "major": "软件工程",
        "graduation_year": "2021", "current_company": "Shopee",
        "current_position": "全栈工程师", "work_years": "4年",
        "employment_status": "在职",
        "current_salary": "32K", "expected_salary": "38K",
        "skills": "React, TypeScript, Node.js, Python, PostgreSQL, MongoDB, AWS, Docker",
        "tech_direction": "全栈", "source": "LinkedIn",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """周天宇 | 男 | 27岁 | 13100009009 | zhouty@qq.com | 深圳

教育背景
2017-2021 深圳大学 软件工程 本科

工作经历
2021.07-至今 Shopee 深圳 | 全栈工程师
- 负责商家后台管理系统（Shopee Seller Center）的前后端开发，服务东南亚 100 万+ 卖家
- 前端用 React + TypeScript，后端用 Node.js + Python（FastAPI）
- 独立完成商品管理模块的全栈重构：从 REST API 设计→数据库 schema→前端交互，重构后页面加载速度提升 40%
- 用 Python 写数据处理脚本：每天定时从 PostgreSQL 拉数据清洗后导入数据仓库，处理 500 万+ 条/天
- 同时也写了很多 Python 自动化测试，对 pytest 比较熟

技能
- 前端：React（精通）、TypeScript（熟练）、Next.js（了解）
- 后端：Node.js（熟练）、Python FastAPI（熟练）、PostgreSQL（熟练）、MongoDB（了解）
- DevOps：Docker（熟练）、AWS（ECS/RDS/Lambda，了解）
- 全栈能力比较均衡，但更喜欢后端——后端的确定性更强，出了问题更好排查"""
    },
    {
        "name": "吴宁", "gender": "男", "age": "26", "phone": "13000010010",
        "email": "wuning@gmail.com", "city": "上海",
        "school": "南京邮电大学", "degree": "本科", "major": "计算机科学与技术",
        "graduation_year": "2022", "current_company": "小红书",
        "current_position": "数据分析师", "work_years": "3年",
        "employment_status": "在职",
        "current_salary": "28K", "expected_salary": "35K",
        "skills": "SQL, Python, Pandas, Hive, Spark, Tableau, A/B测试, 数据挖掘",
        "tech_direction": "数据", "source": "Boss直聘",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """吴宁 | 男 | 26岁 | 13000010010 | wuning@gmail.com | 上海

教育背景
2018-2022 南京邮电大学 计算机科学与技术 本科

工作经历
2022.07-至今 小红书 增长数据团队 | 数据分析师
- 负责小红书用户增长的数据分析：DAU/MAU 趋势、渠道归因、用户分群
- 搭建增长数据看板（Tableau），覆盖 20+ 指标，每天被 GM 和 VP 查看
- 参与推送策略的 A/B 测试分析：发现"个性化文案"比"通用文案"的 CTR 高 34%，推动策略全量上线
- 用 Spark SQL 处理百亿级用户行为日志，构建用户画像标签
- 自学了 Hive + Spark 的调优，把日常跑数流程从 3 小时优化到 40 分钟

项目经历
• 小红书校招数据挑战赛——"用户流失预测"赛道第 3 名，用了 XGBoost + 特征工程
• 为了练 Python 写了个小工具：自动从 HR 系统导出招聘数据做分析（自己在用）

技能
SQL（精通——日常写几百行多表查询）、Python（熟练）、Spark/Hive（熟练）、Tableau（熟练）、A/B 测试（熟练）
- 想转 HR 数据分析方向：因为觉得"人是公司最大的变量"，比增长数据更有意思"""
    },
    {
        "name": "马梓涵", "gender": "女", "age": "25", "phone": "12900011011",
        "email": "mazh@163.com", "city": "北京",
        "school": "中国人民大学", "degree": "硕士", "major": "劳动经济学",
        "graduation_year": "2025", "current_company": "",
        "current_position": "", "work_years": "应届",
        "employment_status": "离职",
        "current_salary": "", "expected_salary": "15K",
        "skills": "Python, R, SQL, Stata, SPSS, 数据分析, 统计建模",
        "tech_direction": "数据", "source": "校招",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """马梓涵 | 女 | 25岁 | 12900011011 | mazh@163.com | 北京

教育背景
2023-2025 中国人民大学 劳动经济学 硕士（研究方向：人力资本与薪酬）
2019-2023 西南财经大学 人力资源管理 本科（GPA 3.7/4.0，专业前 10%）

实习经历
2024.06-2024.09 字节跳动 HR COE | 薪酬分析实习生
- 参与年度薪酬调研：用 Python 分析 5000+ 条薪酬数据，构建分位值模型，对比市场 P50/P75
- 协助计算薪酬带宽：发现某技术序列 P50 低于市场 12%，建议调薪后被采纳
- 用 R 做统计分析：分析绩效分布、离职率与薪酬的相关性等

2023.12-2024.02 某咨询公司 | 人力资本咨询实习生
- 为客户（某央企）做人力资源数据诊断，用 Excel 处理 3 万条员工数据

项目经历
• 硕士论文：《互联网行业薪酬溢价的影响因素研究——基于在线招聘数据的实证分析》
• 在 Coursera 上完成了《Python for Everybody》和《Data Analysis with Python》课程
• 运营一个分享 HR 数据分析知识的公众号，2000+ 关注

技能
Python（Pandas/Matplotlib，熟练）、R（熟练）、SQL（基础）、Stata（熟练）、SPSS（熟练）
- 工具偏学术，但正在补工程能力——在自学 SQL 高级查询和 Tableau"""
    },
    {
        "name": "孙一鸣", "gender": "男", "age": "23", "phone": "12800012012",
        "email": "sunym@qq.com", "city": "杭州",
        "school": "杭州电子科技大学", "degree": "本科", "major": "计算机科学与技术",
        "graduation_year": "2025", "current_company": "",
        "current_position": "", "work_years": "应届",
        "employment_status": "离职",
        "current_salary": "", "expected_salary": "12K",
        "skills": "Python, Django, MySQL, Redis, Docker, Git, Vue.js",
        "tech_direction": "后端", "source": "Boss直聘",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """孙一鸣 | 男 | 23岁 | 12800012012 | sunym@qq.com | 杭州

教育背景
2021-2025 杭州电子科技大学 计算机科学与技术 本科（GPA 3.1/4.0）

实习经历
2024.07-2024.12 网易 杭州 | 后端开发实习生
- 参与网易云音乐内部运营平台的开发，用 Django + MySQL 做后台接口
- 独立完成了一个小模块：歌曲标签管理后台（增删改查 + 批量导入导出），上线后运营同学日常在用
- 写了单元测试，被 mentor 夸"实习生里最注意代码质量的"

项目经历
• 毕业设计：校园二手交易平台（Python Django + Vue.js + MySQL），实现了用户注册登录、商品发布、搜索、聊天、订单管理等功能，GitHub 150+ star
• 参加学校黑客松：用 Flask + 微信小程序做了个课程表助手，获最佳创意奖
• 在 LeetCode 刷了 300+ 题，大部分是中等难度

技能
Python（熟练）、Django（熟练）、MySQL（熟练）、Redis（了解）、Docker（了解）、Vue.js（了解）、Git（熟练）

虽然经验不多，但学习能力很强——Django 是实习前一个月自学的，实习期间独立完成模块开发没出过线上事故。"""
    },

    # ═══════ 低配档：45-64分预期 ═══════ (5人)
    {
        "name": "郑博文", "gender": "男", "age": "31", "phone": "12700013013",
        "email": "zhengbw@126.com", "city": "西安",
        "school": "西安电子科技大学", "degree": "本科", "major": "电子信息工程",
        "graduation_year": "2017", "current_company": "中兴",
        "current_position": "测试工程师", "work_years": "8年",
        "employment_status": "在职",
        "current_salary": "18K", "expected_salary": "25K",
        "skills": "Python, Selenium, JMeter, 自动化测试, Linux, SQL基础",
        "tech_direction": "测试", "source": "脉脉",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """郑博文 | 男 | 31岁 | 12700013013 | zhengbw@126.com | 西安

教育背景
2013-2017 西安电子科技大学 电子信息工程 本科

工作经历
2017.07-至今 中兴通讯 | 测试工程师 → 高级测试工程师
- 负责通信设备网管系统的测试工作，写自动化测试脚本（Python + Selenium）
- 8 年写了一千多个测试用例，但对系统架构和业务逻辑理解较浅——模块怎么实现的不太清楚
- 最近两年开始写一些 Python 脚本帮团队处理日志、生成测试报告，对编程有了兴趣，想转后端开发
- 工作中没用过 Web 框架，没做过需求开发，没操作过数据库（测试环境是别人搭好的）

转行说明
- 正在自学 Python 后端：B 站上看了 Flask 的教学视频，跟着敲了一遍
- 在新手阶段——能写简单接口，但对数据库设计、分布式、性能优化完全没有概念
- 想找一个愿意培养新人的团队"""
    },
    {
        "name": "钱雪", "gender": "女", "age": "28", "phone": "12600014014",
        "email": "qianxue@163.com", "city": "重庆",
        "school": "重庆邮电大学", "degree": "本科", "major": "信息管理与信息系统",
        "graduation_year": "2020", "current_company": "某传统制造企业",
        "current_position": "IT专员", "work_years": "5年",
        "employment_status": "在职",
        "current_salary": "10K", "expected_salary": "18K",
        "skills": "Excel, SQL基础, Python基础, ERP系统, SAP",
        "tech_direction": "数据", "source": "Boss直聘",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """钱雪 | 女 | 28岁 | 12600014014 | qianxue@163.com | 重庆

教育背景
2016-2020 重庆邮电大学 信息管理与信息系统 本科

工作经历
2020.07-至今 某传统制造企业（500人） | IT专员
- 负责公司 ERP 系统的日常运维：账号管理、权限设置、打印问题排查
- 帮 HR 部门做过几个 Excel 的宏（VBA），简化了考勤统计流程
- 用 Excel 做各部门的月度人力报表（没做过数据分析，就是做表）
- 公司用的 SAP，会基础操作但不会后台开发

转行说明
- 想从传统 IT 运维跳到互联网数据分析岗位
- 自学了 Python 基础（会写 for 循环、读 CSV），SQL 刚学到 JOIN
- 在 B 站上看了几个数据分析的视频，Tableau 没摸过
- 能力现状：会用 Excel，Python 和 SQL 都是入门水平，无实际数据分析项目经验"""
    },
    {
        "name": "冯浩", "gender": "男", "age": "33", "phone": "12500015015",
        "email": "fenghao@qq.com", "city": "武汉",
        "school": "武汉理工大学", "degree": "大专", "major": "计算机网络",
        "graduation_year": "2014", "current_company": "某外包公司",
        "current_position": "Java开发", "work_years": "11年",
        "employment_status": "在职",
        "current_salary": "12K", "expected_salary": "15K",
        "skills": "Java, Spring, MySQL, HTML, jQuery",
        "tech_direction": "后端", "source": "Boss直聘",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """冯浩 | 男 | 33岁 | 12500015015 | fenghao@qq.com | 武汉

教育背景
2011-2014 武汉某职业技术学院（现合并到武汉理工大学） 计算机网络 大专

工作经历
2014-至今 一直在各外包公司之间流转，共待过 6 家公司，平均每家公司不到 2 年

最近的经历：
2022.03-至今 某外包公司（驻场某银行） | Java 开发
- 负责银行内部系统的维护：改 Bug、加小功能、写 SQL 查数据
- 技术栈是 10 年前的：Struts2 + Spring + jQuery，连 Spring Boot 都没用过
- 日常工作主要是改改前端页面、写简单的增删改查接口

早些年还干过半年运维、半年技术支持——职业方向比较杂，没有深耕

技能与技术
- Java（写了 10 年，但仅限于基础的增删改查，没用过微服务和分布式）
- MySQL（会写基础查询，不会优化）、HTML/jQuery（会改页面）、Python（没用过）
- 没有 GitHub，没有博客，没有系统自学过新技术
- 想转 Python 后端主要是觉得"Python 好找工作"，没有任何 Python 项目"""
    },
    {
        "name": "沈思", "gender": "女", "age": "27", "phone": "12400016016",
        "email": "shensi@126.com", "city": "成都",
        "school": "四川农业大学", "degree": "本科", "major": "人力资源管理",
        "graduation_year": "2022", "current_company": "某教育机构",
        "current_position": "HR专员", "work_years": "3年",
        "employment_status": "在职",
        "current_salary": "8K", "expected_salary": "12K",
        "skills": "Excel, 招聘, 考勤, 员工关系, 劳动法",
        "tech_direction": "全栈", "source": "Boss直聘",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """沈思 | 女 | 27岁 | 12400016016 | shensi@126.com | 成都

教育背景
2018-2022 四川农业大学 人力资源管理 本科

工作经历
2022.07-至今 某教育机构（200人） | HR专员
- 负责招聘：从筛简历→约面试→发 Offer，每月大概招 10-15 人
- 负责考勤统计和薪酬核算（Excel 做）
- 员工入离职手续办理
- 公司没有 HR 系统，所有数据都在 Excel 里手动维护——效率低但也不知道怎么改进

为什么想转 HR 数据分析
- 做了 3 年 HR 后意识到"拍脑袋"决策的问题：为什么有的人离职？哪个渠道招来的人最好用？没有数据回答
- 想学会用数据驱动 HR 决策，但完全是技术小白——不会 SQL、不会 Python、没用过任何 BI 工具
- 最近开始在 B 站上自学 Excel 数据透视表和基础 SQL
- 学习能力和适应性还可以（HR 全模块都是自学的），但技术底子确实薄弱"""
    },
    {
        "name": "韩天乐", "gender": "男", "age": "26", "phone": "12300017017",
        "email": "hantianle@163.com", "city": "北京",
        "school": "北京联合大学", "degree": "本科", "major": "电子商务",
        "graduation_year": "2022", "current_company": "某MCN机构",
        "current_position": "运营专员", "work_years": "3年",
        "employment_status": "在职",
        "current_salary": "12K", "expected_salary": "20K",
        "skills": "运营, 内容策划, 拍摄剪辑, Excel, 基础Python",
        "tech_direction": "数据", "source": "Boss直聘",
        "target_position": "数据分析师（HR方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """韩天乐 | 男 | 26岁 | 12300017017 | hantianle@163.com | 北京

教育背景
2018-2022 北京联合大学 电子商务 本科

工作经历
2022.08-至今 某 MCN 机构 | 运营专员
- 负责抖音账号的日常运营：选题策划、脚本撰写、数据复盘
- 用 Excel 管理 50+ 达人的排期和商务合作
- 看过一些"数据分析师转行"的视频，觉得数据岗钱多事少，想转

技能与技术
- Excel：会 VLOOKUP、数据透视表
- Python：在 B 站上跟了 5 节课，会 print("hello world") 的程度
- SQL：完全不会
- 运营做得还行但谈不上出色——达人数据复盘就是看看播放量点赞量，没有做过真正的数据分析

自我评价
- 感觉运营行业天花板低，想转技术岗
- 但对数据分析工作的理解很可能是错的——觉得就是"做做表、画个图表"
- 对数据库、统计学、Python 这些硬技能的难度没有概念"""
    },

    # ═══════ 不匹配档：20-44分预期 ═══════ (3人)
    {
        "name": "朱宇", "gender": "男", "age": "24", "phone": "12200018018",
        "email": "zhuyu@qq.com", "city": "上海",
        "school": "某二本院校", "degree": "本科", "major": "英语",
        "graduation_year": "2024", "current_company": "",
        "current_position": "", "work_years": "应届",
        "employment_status": "离职",
        "current_salary": "", "expected_salary": "10K",
        "skills": "英语专八, Office, 基础HTML",
        "tech_direction": "前端", "source": "Boss直聘",
        "target_position": "产品经理（AI应用方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """朱宇 | 男 | 24岁 | 12200018018 | zhuyu@qq.com | 上海

教育背景
2020-2024 某二本院校 英语 本科

实习经历
2023.09-2023.12 某翻译公司 | 翻译实习生
- 翻译技术文档（英译中）和商务邮件
- 帮公司网站更新过内容（用 WordPress 后台，不需要写代码）

校园经历
- 担任学院学生会外联部部长——拉过赞助，组织过几次活动
- 参加学校英语演讲比赛获二等奖

为什么投产品经理
- 觉得产品经理"不用写代码也能进互联网"
- 没有系统学习过产品知识——没写过 PRD、没画过原型、没做过用户调研
- 对 AI 的理解停留在"用过 ChatGPT"
- 英语好算是唯一亮点，但和岗位要求基本不沾边"""
    },
    {
        "name": "蒋明", "gender": "男", "age": "35", "phone": "12100019019",
        "email": "jiangming@163.com", "city": "长沙",
        "school": "中南大学", "degree": "本科", "major": "机械设计制造",
        "graduation_year": "2013", "current_company": "三一重工",
        "current_position": "机械工程师", "work_years": "12年",
        "employment_status": "在职",
        "current_salary": "15K", "expected_salary": "30K",
        "skills": "CAD, SolidWorks, 有限元分析, 机械设计",
        "tech_direction": "后端", "source": "脉脉",
        "target_position": "Python后端开发工程师",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """蒋明 | 男 | 35岁 | 12100019019 | jiangming@163.com | 长沙

教育背景
2009-2013 中南大学 机械设计制造及其自动化 本科

工作经历
2013.07-至今 三一重工 | 机械工程师
- 12 年机械设计经验，设计过挖掘机和起重机的液压系统
- 带过 5 人设计小组，主导过 2 款新机型的机械结构设计
- 会 CAD 和 SolidWorks，画图能力一流

为什么投 Python 后端
- 在抖音上看到"零基础转行程序员 3 个月上岸"的视频，觉得可以试试
- 没有任何编程基础——没写过 Hello World，分不清 Python 和 JavaScript
- 对互联网公司和软件开发的工作方式完全不了解
- 期望薪资 30K 可能是因为听说"程序员工资高"，但没有意识到自己等于零基础"""
    },
    {
        "name": "邓伟", "gender": "男", "age": "29", "phone": "12000020020",
        "email": "dengwei@qq.com", "city": "广州",
        "school": "广州大学", "degree": "本科", "major": "市场营销",
        "graduation_year": "2019", "current_company": "某房地产中介",
        "current_position": "销售经理", "work_years": "6年",
        "employment_status": "在职",
        "current_salary": "8K", "expected_salary": "25K",
        "skills": "销售, 客户管理, 谈判, Excel",
        "tech_direction": "前端", "source": "Boss直聘",
        "target_position": "AI算法工程师（大模型方向）",
        "interview_status": "筛选", "has_top_papers": 0,
        "resume_text": """邓伟 | 男 | 29岁 | 12000020020 | dengwei@qq.com | 广州

教育背景
2015-2019 广州大学 市场营销 本科

工作经历
2019.07-至今 辗转了 3 家房地产中介公司 | 销售→销售经理
- 在链家干了 1.5 年，贝壳干了 2 年，现在在一家小中介公司
- 业绩中等——最好的时候一个月卖了 3 套房
- 带过 3 个人的小团队
- 对技术和编程完全是空白，投"AI算法工程师"可能是因为被 AI 的薪资吸引了

技能
- 唯一和技术沾边的：会用 Excel 做客户跟进表
- 自称"对 AI 感兴趣"，但问他"什么是机器学习"回答不出来
- 没有任何数学或编程基础，大学高数刚好及格"""
    },
]


# ============================================================
# 主流程
# ============================================================
def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 1. 清空旧数据
    cur.execute("DELETE FROM jobs")
    cur.execute("DELETE FROM resumes")
    cur.execute("DELETE FROM evaluations")
    conn.commit()

    # 2. 写入岗位
    for job in JOBS:
        cur.execute("""
            INSERT INTO jobs (title, jd_text, requirements, department)
            VALUES (?, ?, ?, ?)
        """, (job["title"], job["jd_text"], job["requirements"], job["department"]))
    print(f"[OK] 已写入 {len(JOBS)} 个岗位")

    # 3. 写入简历
    for i, c in enumerate(CANDIDATES):
        code = f"CV-202606{21+i:02d}"
        cur.execute("""
            INSERT INTO resumes (
                unique_code, name, gender, age, phone, email, city,
                school, degree, major, graduation_year,
                current_company, current_position,
                work_years, employment_status,
                current_salary, expected_salary,
                skills, tech_direction, source,
                target_position, interview_status,
                hr_notes, resume_text, has_top_papers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            code,
            c["name"], c["gender"], c["age"], c["phone"], c["email"], c["city"],
            c["school"], c["degree"], c["major"], c["graduation_year"],
            c["current_company"], c["current_position"],
            c["work_years"], c["employment_status"],
            c["current_salary"], c["expected_salary"],
            c["skills"], c["tech_direction"], c["source"],
            c["target_position"], c["interview_status"],
            "", c["resume_text"], c["has_top_papers"],
        ))

    conn.commit()
    conn.close()

    # 统计
    from collections import Counter
    stats = Counter(c["interview_status"] for c in CANDIDATES)
    target_stats = Counter(c["target_position"] for c in CANDIDATES)

    print(f"[OK] 已写入 {len(CANDIDATES)} 份简历")
    print(f"  状态分布: {dict(stats)}")
    print(f"  岗位分布: {dict(target_stats)}")
    print(f"\n数据生成完成！启动 python app.py 即可看到效果。")


if __name__ == "__main__":
    main()
