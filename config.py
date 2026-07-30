# config.py — 配置（API Key 从环境变量读取，本文件不上传 GitHub）

import os
from dotenv import load_dotenv
load_dotenv()  # 自动读取项目目录下的 .env 文件

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
_API_KEY_MISSING = not bool(API_KEY)
if _API_KEY_MISSING:
    print("=" * 55)
    print("⚠  DEEPSEEK_API_KEY 未设置 — AI 功能将不可用")
    print("   创建 .env 文件并写入 DEEPSEEK_API_KEY=sk-xxx")
    print("   没有 Key 也能浏览演示数据和 UI（演示模式）")
    print("=" * 55)
API_URL = "https://api.deepseek.com/chat/completions"

DB_NAME = "resume_screening.db"
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB 上传限制
DEFAULT_MAX_TOKENS = 2000              # AI 评分默认输出长度
ANALYTICS_MAX_TOKENS = 4000            # AI 分析输出长度

DIMENSIONS = {
    "技能匹配度": 40,
    "经验相关性": 25,
    "学历匹配度": 15,
    "项目成果质量": 10,
    "稳定性成长性": 10,
}
