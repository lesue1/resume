"""
ai_scorer.py — DeepSeek API 简历评分
=====================================

本质：发一个 HTTP POST 请求给 DeepSeek 服务器，把 JD 和简历文本传过去，
让 AI 按 5 个维度打分，返回 JSON。

完整链路：
  1. build_prompt(jd, resume)       → 构造给 AI 的提示词
  2. call_deepseek(prompt)          → 发 HTTP 请求，拿到 AI 返回的 JSON
  3. calculate_total(scores_dict)   → 5维度分数 × 权重 = 总分
  4. score_resume(jd, resume)       → 把上面三步串起来，一个函数搞定
"""

import json
import requests
import config

API_KEY = config.API_KEY
API_URL = config.API_URL
DIMENSIONS = config.DIMENSIONS  # {"技能匹配度": 40, "经验相关性": 25, ...}


# =============================================================================
# 1. 构造 Prompt — 告诉 AI 该干什么
# =============================================================================

SYSTEM_PROMPT = """你是一位资深 HR 专家和猎头顾问，拥有 15 年技术岗位招聘经验，曾为字节跳动、腾讯等公司招聘过上千名技术人才。

## 你的能力
你对技术栈非常熟悉，能一眼看出候选人技能是否匹配岗位需求。你擅长从简历的字里行间挖掘候选人的真实能力和潜在风险点。

## 评分规则
请根据以下 5 个维度给候选人打分（每个维度 0-100 分）。评分要拉开差距——不要所有人都在 70-85 之间。优秀的给 90+，明显不匹配的给 40 以下。

### 1. 技能匹配度（权重 40%）
候选人的技术栈是否匹配岗位需求？
- 硬技能覆盖度：要求的编程语言、框架、工具，候选人会哪些？缺哪些？
- 技能深度：是"了解"级别还是"精通"级别？有没有深层原理的体现？
- 行业 know-how：对所在赛道的理解——技术选型原因？架构设计思路？
- 如果 JD 未提供，则根据简历推断最匹配的技术方向并以此为标准评分

### 2. 经验相关性（权重 25%）
工作经验和项目经历和岗位要求的相关度
- 业务相似度：做过同类产品/业务吗？（比如岗位做支付，候选人也做过支付）
- 职位匹配：之前职位和现在招的岗位在职责上有多少重叠？
- 项目规模：参与或主导过多大用户量/多高并发的项目？
- 团队角色：独立贡献还是带过人？对团队的影响力如何？

### 3. 学历匹配度（权重 15%）
教育背景和专业的匹配程度
- 学历层次：博士/硕士/本科/大专
- 专业相关性：计算机/软件工程（高匹配）vs 相关理工科（中等）vs 完全不相关（低）
- 学校背景：985/211 加分但不是决定性因素
- 持续学习：有培训证书、自学记录、技术博客等可弥补学历不足

### 4. 项目成果质量（权重 10%）
过往项目是否有具体、可量化的成果
- 数据化成果：有没有"提升了 30%"、"节省了 50 万"、"日活 200 万"这类具体数字？
- 业务影响：项目对公司/产品的实际贡献，是不是核心链路？
- 技术深度：解决了什么技术难题？方案有什么创新点？
- 没有数字的项目不等于没价值——但要明确指出"简历缺少量化成果，建议面试时追问"

### 5. 稳定性成长性（权重 10%）
职业发展轨迹和长期潜力
- 跳槽频率：平均每段工作多长时间？一年一跳需要警惕
- 成长斜率：从初级到高级的晋升速度？职责范围是否在扩大？
- 学习能力：是否持续跟进新技术？GitHub、技术博客、开源贡献？
- 职业规划：跳槽逻辑是否清晰？（比如从小公司到大厂，从传统到互联网）

## 输出格式（严格遵守 JSON，不要任何其他内容，不要 markdown 标记）
{
  "技能匹配度": {
    "score": 85,
    "reason": "1-2句：具体掌握/缺失的技能，最突出的亮点。50-80字"
  },
  "经验相关性": {
    "score": 70,
    "reason": "1-2句：业务匹配度+项目规模，一句话说清。50-80字"
  },
  "学历匹配度": {
    "score": 80,
    "reason": "1-2句：学历专业+持续学习情况。50-80字"
  },
  "项目成果质量": {
    "score": 65,
    "reason": "1-2句：量化成果+项目影响力。50-80字"
  },
  "稳定性成长性": {
    "score": 75,
    "reason": "1-2句：跳槽频率+成长轨迹。50-80字"
  },
  "综合评语": "3-4句话：①核心优势（1个）②主要风险（1个）③推荐评级。100-150字",
  "优势亮点": ["候选人最突出的2-3个优势，每条8-15字"],
  "风险点": ["需要关注的2-3个潜在问题，每条8-15字"],
  "面试建议": [
    {"问题": "具体面试问题1", "考察点": "通过这个问题考察什么", "关注点": "好的回答应该包含什么"},
    {"问题": "具体面试问题2", "考察点": "...", "关注点": "..."},
    {"问题": "具体面试问题3", "考察点": "...", "关注点": "..."}
  ]
}

## 铁律
- reason 必须点名具体技术/项目/数据，不能写"技术能力强"这种正确的废话
- 信息缺失的地方诚实标注"简历未提及XX"，不要自己脑补
- 应届生经验少不是错——评价标准应该是"在同届里什么水平"
- 不要平权打分——有亮点的冲高分，明显不行的果断给低分"""


def build_prompt(jd_text, resume_text):
    """把 JD 和简历文本拼成最终发给 AI 的消息。

    返回 OpenAI 兼容格式的 messages 列表：
    [
        {"role": "system", "content": "你是HR专家..."},    ← 角色设定
        {"role": "user",   "content": "JD:...\n简历:..."}   ← 具体任务
    ]

    这么设计是因为 AI 模型区分"永久指令"和"具体任务"：
    - system = 不管用户说什么，这个角色设定始终不变
    - user   = 每次评分都不一样的内容（JD + 简历）
    """
    user_message = f"""请对以下候选人进行评分：

【岗位 JD】
{jd_text.strip() or "（未提供岗位描述，请根据简历内容综合评估）"}

【候选人简历】
{resume_text.strip()}

请严格按照 JSON 格式输出评分结果。"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


# =============================================================================
# 2. 调用 DeepSeek API
# =============================================================================

def call_deepseek(messages, temperature=0.3):
    """调用 DeepSeek Chat API，返回 AI 的文本回复。

    参数:
        messages: build_prompt() 返回的消息列表
        temperature: 0-1，越低越稳定保守，越高越天马行空。
                     评分任务要客观一致 → 用 0.3

    DeepSeek API 完全兼容 OpenAI 的接口格式，所以用标准的
    POST /chat/completions，Header 带 Authorization: Bearer xxx

    返回:
        str: AI 的回复文本，或者 None（调用失败时）
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    payload = {
        "model": "deepseek-chat",  # DeepSeek 的对话模型
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2000,         # 评分结果含多个字段，1000 不够
        "stream": False,            # 不流式，等完整结果
    }

    try:
        # requests.post(url, json=dict, timeout=秒)
        # json= 参数会自动把 dict 转成 JSON 字符串，并设 Content-Type 为 application/json
        # timeout=60 = 最多等 60 秒，超时就报错（防止一直卡着）
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

        # HTTP 状态码检查：200 = 成功，401 = Key不对，429 = 用太快，500 = 服务器炸了
        if response.status_code != 200:
            print(f"[ERROR] API 返回错误 {response.status_code}: {response.text[:200]}")
            return None

        # 解析返回的 JSON，提取 AI 的实际回复
        data = response.json()
        # data 的结构：
        # {
        #   "choices": [{"message": {"content": "AI的回复文本", "role": "assistant"}}],
        #   "usage": {"prompt_tokens": 500, "completion_tokens": 200, ...}
        # }
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        print("[ERROR] API 请求超时（60秒），检查网络或稍后重试")
        return None
    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接 DeepSeek API，检查网络")
        return None
    except Exception as e:
        print(f"[ERROR] API 调用异常: {e}")
        return None


def call_deepseek_stream(messages, temperature=0.5):
    """流式调用 DeepSeek API，逐块 yield 文本内容。

    用 requests 的 stream=True，每收到一行 "data: {...}"
    就解析出 delta.content，yield 出去。

    用法: for chunk in call_deepseek_stream(messages): print(chunk, end='')
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1500,
        "stream": True,  # ← 关键：开启流式
    }

    try:
        # stream=True 让 requests 不立即下载完整响应体，而是逐块读取
        response = requests.post(
            API_URL, headers=headers, json=payload,
            timeout=90, stream=True
        )

        if response.status_code != 200:
            print(f"[ERROR] 流式 API 返回 {response.status_code}: {response.text[:200]}")
            yield None
            return

        # 逐行读 SSE 流
        # 格式：data: {"choices":[{"delta":{"content":"你好"}}]}\n\n
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            json_str = line[6:]  # 去掉 "data: " 前缀
            if json_str == "[DONE]":
                break

            try:
                chunk = json.loads(json_str)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    except requests.exceptions.Timeout:
        print("[ERROR] 流式请求超时")
        yield None
    except requests.exceptions.ConnectionError:
        print("[ERROR] 流式连接失败")
        yield None
    except Exception as e:
        print(f"[ERROR] 流式调用异常: {e}")
        yield None


# =============================================================================
# 3. 解析 AI 返回 + 计算总分
# =============================================================================

def _find_json_end(text, start):
    """从 start 位置开始，用括号计数找到匹配的 }（忽略字符串内的花括号）。"""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1


def parse_response(raw_text):
    """把 AI 返回的文本解析成 Python 字典。

    AI 返回的是 Markdown 代码块包裹的 JSON，也可能直接返回 JSON。
    先试试直接解析，不行就提取 ``` 之间的内容。

    返回:
        dict 或 None
    """
    if not raw_text:
        return None

    text = raw_text.strip()

    # ── 尝试 1：直接解析 ──
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # ── 尝试 2：提取 ```json ... ``` 之间的内容 ──
    start = text.find("```json")
    if start == -1:
        start = text.find("```")

    if start != -1:
        start = text.find("{", start)
        if start != -1:
            end = _find_json_end(text, start)
            if end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

    # ── 尝试 3：直接在原文中用括号匹配找 JSON ──
    start = text.find("{")
    if start != -1:
        end = _find_json_end(text, start)
        if end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    print(f"[ERROR] 无法解析 AI 返回的 JSON: {text[:200]}...")
    return None


def calculate_score(scores_dict):
    """根据 5 维分数和权重计算加权总分。

    加权总分 = Σ(各维度分数 × 权重/100)

    例如：
        技能匹配度 85 × 0.40 = 34.0
        经验相关性 70 × 0.25 = 17.5
        学历匹配度 80 × 0.15 = 12.0
        项目成果质量 65 × 0.10 = 6.5
        稳定性成长性 75 × 0.10 = 7.5
        总分 = 77.5
    """
    total = 0.0
    for dim_name, weight in DIMENSIONS.items():
        dim_data = scores_dict.get(dim_name, {})
        # dim_data 是 {"score": 85, "reason": "..."}
        # .get() 兜底——如果 AI 没返回某个维度，默认 0 分
        score = dim_data.get("score", 0) if isinstance(dim_data, dict) else 0
        total += score * (weight / 100.0)

    return round(total, 1)  # 只保留 1 位小数


# =============================================================================
# 4. 一站式评分 — 把上面三步串起来
# =============================================================================

def score_resume(jd_text, resume_text):
    """一站式：JD + 简历文本 → AI 评分 → 解析 → 计算总分。

    这是对外的主要接口，app.py 只需要调这一个函数。

    参数:
        jd_text: 岗位描述（纯文本）
        resume_text: 简历内容（从 PDF 提取的纯文本）

    返回:
        dict: {
            "success": True/False,
            "total_score": 77.5,
            "scores": {
                "技能匹配度": {"score": 85, "reason": "..."},
                ...
            },
            "summary": "综合评语",
            "error": None 或 "错误信息",
            "tokens_used": {"prompt": 500, "completion": 200, "total": 700}
        }
    """
    result = {
        "success": False,
        "total_score": 0,
        "scores": {},
        "summary": "",
        "error": None,
        "tokens_used": {},
    }

    # Step 1: 构造 Prompt
    messages = build_prompt(jd_text, resume_text)

    # Step 2: 调用 API
    raw_response = call_deepseek(messages)

    if raw_response is None:
        result["error"] = "AI 接口调用失败，请检查网络或 API Key"
        return result

    # Step 3: 解析 JSON
    scores = parse_response(raw_response)

    if scores is None:
        result["error"] = f"AI 返回格式异常: {raw_response[:200]}"
        return result

    # 验证 5 个维度是否齐全
    missing_dims = [dim for dim in DIMENSIONS if dim not in scores]
    if missing_dims:
        result["error"] = f"AI 返回缺少维度: {', '.join(missing_dims)}"
        return result

    # Step 4: 计算加权总分
    result["total_score"] = calculate_score(scores)
    # 维度评分和附加字段分开
    result["scores"] = {k: v for k, v in scores.items() if k not in ("综合评语", "优势亮点", "风险点", "面试建议")}
    result["summary"] = scores.get("综合评语", "")
    result["highlights"] = scores.get("优势亮点", [])
    result["risks"] = scores.get("风险点", [])
    result["interview_questions"] = scores.get("面试建议", [])
    result["success"] = True

    return result


# =============================================================================
# 5. 追问功能 — 评分后进一步了解候选人
# =============================================================================

FOLLOWUP_SYSTEM_PROMPT = """你是一位资深面试官，正在和同事讨论一个候选人。你刚评估完这份简历。

## 回答原则

1. **先直接回答问题**：对方问什么就答什么，别绕。问"他以前实习多久"就回答简历上写的几个月，别扯JD要求
2. **严格区分简历和JD**：简历是候选人的经历，JD 是岗位要求。问简历的事就只看简历，别把 JD 的要求当成候选人的事实
3. **基于简历事实**：简历写了的就是写了，没写的就说"简历未提及"
4. **再补充上下文**：答完之后，如果觉得有必要，用一两句话补充
5. **别每次都列点**：简单问题一句话就够了。只有对方问"分析一下"、"评估一下"这类开放问题时，才用结构化回答

## 结构化回答（仅在开放问题时使用）
- **核心结论：**一句话
- **具体分析：**2-3 个要点
- **面试建议：**1-2 条

## 字数
简单问题 30-80 字，开放问题 150-250 字。像同事聊天，别整得像论文答辩。"""


def _build_scores_context(scores_context):
    """把评分结果转成可读文本，供追问时给 AI 参考。"""
    if isinstance(scores_context, dict):
        ctx_lines = [f"总分: {scores_context.get('total_score', 'N/A')}"]
        for dim, data in scores_context.get('scores', {}).items():
            ctx_lines.append(f"- {dim}: {data.get('score', '?')}分 — {data.get('reason', '')}")
        ctx_lines.append(f"综合评语: {scores_context.get('summary', '')}")
        return "\n".join(ctx_lines)
    return str(scores_context)


def _build_followup_user_message(resume_text, jd_text, scores_context, question, markdown=False):
    """构建追问的 user message（ask_followup 和 ask_followup_stream 共用）。"""
    ctx_text = _build_scores_context(scores_context)
    md_hint = "请用 Markdown 格式组织回答。" if markdown else ""
    return f"""以下是候选人的简历内容和之前的评分结果：

【评分结果】
{ctx_text}

【岗位 JD】
{jd_text.strip() or "（未提供）"}

【简历原文】
{resume_text.strip()}

【面试官的追问】
{question}

请基于以上信息回答。如果简历中没有相关内容，诚实告知并给出面试建议。{md_hint}"""


def ask_followup(resume_text, jd_text, scores_context, question):
    """基于简历内容和评分结果，回答关于候选人的追问。"""
    user_message = _build_followup_user_message(resume_text, jd_text, scores_context, question)
    messages = [
        {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    return call_deepseek(messages, temperature=0.5)


def ask_followup_stream(resume_text, jd_text, scores_context, question):
    """流式版本——逐 token yield，用于 SSE 推送到前端。"""
    user_message = _build_followup_user_message(resume_text, jd_text, scores_context, question, markdown=True)
    messages = [
        {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    yield from call_deepseek_stream(messages, temperature=0.5)


# =============================================================================
# 自测：用一段假简历跑一次评分（确认 API 通不通）
# =============================================================================
if __name__ == "__main__":
    # 假 JD
    test_jd = """
    岗位：Python 后端开发工程师
    要求：精通 Python、Flask/Django，熟悉 MySQL/PostgreSQL，
          了解 Docker、Linux，2年以上后端开发经验，
          有 AI/ML 项目经验优先。
    """

    # 假简历（模拟 PDF 提取出来的文本）
    test_resume = """
    张三 | 135-0000-0000 | zhangsan@email.com

    教育背景：
    2019-2023  四川农业大学  计算机科学与技术  本科

    工作经验：
    2023-至今  某科技公司  Python 开发工程师
    - 使用 Flask 开发内部管理系统，日活 2000+
    - 基于 Scikit-learn 构建客户流失预测模型，准确率 87%
    - 负责 PostgreSQL 数据库设计和慢查询优化

    技能：
    Python, Flask, Docker, PostgreSQL, Redis, Scikit-learn, Git
    """

    print("=" * 50)
    print("AI 简历评分自测")
    print("=" * 50)
    print(f"JD 长度: {len(test_jd)} 字符")
    print(f"简历长度: {len(test_resume)} 字符")
    print("-" * 50)

    result = score_resume(test_jd, test_resume)

    if result["success"]:
        print(f"总分: {result['total_score']}")
        print()
        for dim, data in result["scores"].items():
            bar = "#" * (data["score"] // 5) + "-" * (20 - data["score"] // 5)
            print(f"  {dim:<8s} {bar} {data['score']}分")
            print(f"          {data['reason']}")
        print(f"\n综合评语: {result['summary']}")
    else:
        print(f"失败: {result['error']}")
