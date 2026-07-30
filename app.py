"""
app.py — Flask 主应用
=====================
一个文件跑起整个 Web 应用。

启动方式：
    python app.py
然后浏览器打开 http://localhost:5000

架构：Flask 路由 + HTMX 局部刷新 + Jinja2 模板渲染
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, make_response
import os
import io
import time
import threading

# ── 简易频率限制（in-memory，单进程，重启清零） ──
_rate_window = {}   # ip → [(timestamp, endpoint), ...]
_rate_lock = threading.Lock()

# 限制规则：key=endpoint, value=(window_seconds, max_requests)
RATE_LIMITS = {
    "/api/score":       (60, 10),    # AI 评分：每分钟最多 10 次（最贵）
    "/api/followup":    (60, 15),    # 追问：每分钟最多 15 次
    "/api/ai-summary":  (60, 5),     # AI 分析：每分钟最多 5 次
    "/api/resumes/import": (60, 20), # 批量导入：每分钟最多 20 次
    "/api/parse-pdf":   (60, 30),    # PDF 解析：每分钟最多 30 次
    "/api/batch/import": (60, 15),   # 批量文件上传解析
    "/api/batch/quick-filter": (60, 30),  # 关键词匹配（免费）
    "/api/batch/score": (60, 8),     # 批量 AI 评分
    "default":          (60, 60),    # 其他 API：每分钟最多 60 次
}

def check_rate_limit(ip, endpoint):
    """检查是否超过频率限制。返回 (allowed, retry_after_seconds)。"""
    with _rate_lock:
        now = time.time()
        rule = RATE_LIMITS.get(endpoint, RATE_LIMITS["default"])
        window, max_req = rule

        if ip not in _rate_window:
            _rate_window[ip] = []
        # 清理过期记录
        _rate_window[ip] = [r for r in _rate_window[ip] if now - r[0] < window]
        # 检查
        count = len([r for r in _rate_window[ip] if r[1] == endpoint])
        if count >= max_req:
            oldest = min(r[0] for r in _rate_window[ip] if r[1] == endpoint)
            retry_after = int(window - (now - oldest)) + 1
            return False, max(retry_after, 1)
        # 记录本次请求
        _rate_window[ip].append((now, endpoint))
        return True, 0
import csv
import json
import re
import uuid
import html as _html

# 导入自己的模块
import config
from database import (
    init_db, get_conn, get_evaluations, get_evaluations_for_resume,
    save_evaluation, get_resumes, update_status, delete_resume, save_resume,
    get_analytics_data, migrate_legacy_data,
    save_job, get_jobs, get_job, delete_job,
    get_stages, save_stage, delete_stage, reorder_stages,
)
from pdf_parser import extract_text, extract_resume_text
from ai_scorer import score_resume, ask_followup, ask_followup_stream
from keyword_matcher import quick_match_batch

# ── OCR 模块（需 Tesseract 系统安装 + Pillow） ──

class OCRService:
    """OCR 识别服务——封装 Tesseract CLI 调用和状态检查。"""

    def __init__(self):
        self.available = False
        self.error = ""
        self._tesseract_exe = None
        self._tessdata_dir = ""
        try:
            from PIL import Image
            import os as _os
            import shutil as _shutil
            self.Image = Image
            # 先查 PATH 里的 tesseract，找不到再用常见路径兜底
            exe = _shutil.which("tesseract")
            if exe:
                self._tesseract_exe = exe
            elif _os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
                self._tesseract_exe = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            elif _os.path.exists(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
                self._tesseract_exe = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            elif _os.path.exists("/usr/bin/tesseract"):
                self._tesseract_exe = "/usr/bin/tesseract"
            elif _os.path.exists("/usr/local/bin/tesseract"):
                self._tesseract_exe = "/usr/local/bin/tesseract"
            else:
                self.error = ("Tesseract 未安装 — 请从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装，"
                       "安装时勾选中文语言包，安装后重启本应用")
                return
            # tessdata 优先用环境变量，其次用可执行文件旁边的路径
            self._tessdata_dir = _os.environ.get("TESSDATA_PREFIX", "")
            self.available = True
        except ImportError:
            self.error = "缺少 Pillow 模块，请运行 pip install Pillow"

    def process(self, file_stream):
        """上传图片 → OCR 识别 → 返回 (success, text_or_error)。"""
        if not self.available:
            return False, f"OCR 不可用: {self.error}"

        import tempfile, subprocess, os as _os

        img_path = None
        out_base = None
        try:
            img = self.Image.open(file_stream)
            w, h = img.size
            if max(w, h) > 2000:
                ratio = 2000 / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), self.Image.LANCZOS)

            fd, img_path = tempfile.mkstemp(suffix='.png')
            _os.close(fd)
            img.save(img_path, 'PNG')

            fd, out_base = tempfile.mkstemp(suffix='')
            _os.close(fd)

            subprocess.run([
                self._tesseract_exe,
                img_path, out_base,
                "--tessdata-dir", self._tessdata_dir,
                "-l", "chi_sim+eng",
            ], capture_output=True, timeout=30, check=True)

            txt_path = out_base + '.txt'
            if not _os.path.exists(txt_path):
                return False, "OCR 未生成输出文件"

            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read().strip()

            if not text:
                return False, "图片中未识别到文字，确认图片包含清晰的中文或英文"

            return True, text

        except subprocess.TimeoutExpired:
            return False, "识别超时，请使用更小的图片"
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode('utf-8', 'ignore')[:200] if e.stderr else '未知'
            return False, f"OCR 引擎错误: {err_msg}"
        except Exception as e:
            return False, f"识别失败: {str(e)}"
        finally:
            if img_path and _os.path.exists(img_path):
                _os.remove(img_path)
            if out_base:
                txt = out_base + '.txt'
                if _os.path.exists(txt):
                    _os.remove(txt)

_ocr = OCRService()

# ── 创建 Flask 实例 ──
# __name__ 告诉 Flask 当前模块名，Flask 用它来定位 templates/ 和 static/ 文件夹
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH


# ── 全局频率限制（before_request） ──
@app.before_request
def enforce_rate_limit():
    """对所有 /api/ 路由检查频率限制。"""
    if request.path.startswith("/api/"):
        ip = request.remote_addr or "127.0.0.1"
        endpoint = request.path
        # 精确匹配 or 前缀匹配
        if endpoint not in RATE_LIMITS:
            # 试前缀匹配（动态路由如 /api/stages/1/delete）
            for key in RATE_LIMITS:
                if key != "default" and endpoint.startswith(key.rstrip("/")):
                    endpoint = key
                    break
            else:
                endpoint = "default"
        allowed, retry = check_rate_limit(ip, endpoint)
        if not allowed:
            return jsonify({
                "success": False,
                "error": f"请求过于频繁，请 {retry} 秒后重试",
                "retry_after": retry,
            }), 429


def render_page(template_name, **context):
    """HTMX 请求只返回内容片段，浏览器直接访问返回完整页面。"""
    base_name, ext = template_name.rsplit('.', 1)
    template_name = f"{base_name}_v2.{ext}"
    context['page'] = template_name

    content = render_template(template_name, **context)
    if request.headers.get("HX-Request"):
        return content

    return make_response(render_template("base_v2.html", content=content, page=template_name))


# =============================================================================
# 页面路由
# =============================================================================

@app.route("/")
def index():
    """首页直接重定向到数据分析。"""
    return redirect("/analytics")


@app.route("/evaluate")
def evaluate_page():
    return render_page("evaluate.html")


@app.route("/analytics")
def analytics_page():
    return render_page("analytics.html")


@app.route("/resumes")
def resumes_page():
    return render_page("resumes.html")


@app.route("/jobs")
def jobs_page():
    return render_page("jobs.html")


# =============================================================================
# API 路由 — 返回 JSON 或 HTML 片段（HTMX 局部刷新）
# =============================================================================

# ── 岗位 API ──

@app.route("/api/jobs/list")
def api_jobs_list():
    """岗位列表（HTML 片段）或 JSON。"""
    df = get_jobs()
    if request.args.get("format") == "json":
        if df.empty:
            return jsonify([])
        return jsonify(df[['id', 'title', 'department']].to_dict(orient='records'))

    if df.empty:
        return "<p style='color:#999;text-align:center;padding:40px;'>暂无岗位，点击右上角创建</p>"

    cards = ""
    for _, j in df.iterrows():
        cards += f"""
        <div class="job-card" id="job-{j['id']}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:600;">{_html.escape(str(j['title']))}</span>
                <div style="display:flex;gap:8px;">
                    <button class="btn btn-secondary btn-sm" onclick="editJob({j['id']})">编辑</button>
                    <button class="btn btn-sm btn-danger" onclick="confirmDeleteJob({j['id']})">删除</button>
                </div>
            </div>
        </div>
        """
    return cards


@app.route("/api/jobs/save", methods=["POST"])
def api_jobs_save():
    """创建或更新岗位。"""
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误，需要 JSON"}), 400
    try:
        save_job(
            title=data.get("title", "").strip(),
            jd_text=data.get("jd_text", "").strip(),
            requirements=data.get("requirements", "").strip(),
            department=data.get("department", "").strip(),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/jobs/<int:job_id>")
def api_jobs_get(job_id):
    """获取单个岗位详情。"""
    job = get_job(job_id)
    if job:
        return jsonify(job)
    return jsonify({"error": "未找到"}), 404


@app.route("/api/jobs/<int:job_id>/delete", methods=["POST"])
def api_jobs_delete(job_id):
    """删除岗位。"""
    try:
        delete_job(job_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── 管道阶段 API ──

@app.route("/api/stages")
def api_stages():
    """返回所有阶段 JSON。"""
    return jsonify(get_stages())


@app.route("/api/stages/save", methods=["POST"])
def api_stages_save():
    """新建或更新阶段。"""
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400
    try:
        save_stage(
            stage_id=data.get("id"),
            name=data.get("name", "").strip(),
            color=data.get("color", "#0071e3"),
            sort_order=data.get("sort_order", 0),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/stages/reorder", methods=["POST"])
def api_stages_reorder():
    """批量排序。"""
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400
    try:
        reorder_stages(data.get("order", []))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/stages/<int:stage_id>/delete", methods=["POST"])
def api_stages_delete(stage_id):
    """删除阶段。"""
    try:
        delete_stage(stage_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/ocr-check")
def api_ocr_check():
    """检查 OCR 是否可用。"""
    return jsonify({"available": _ocr.available, "error": _ocr.error})


@app.route("/api/ocr-image", methods=["POST"])
def api_ocr_image():
    """上传图片 → OCR 识别 → 返回文本。"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有收到文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"})

    ok, result = _ocr.process(file.stream)
    if ok:
        return jsonify({"success": True, "text": result, "length": len(result)})
    return jsonify({"success": False, "error": result})


# ── AI 评估 API ──

@app.route("/api/parse-pdf", methods=["POST"])
def api_parse_pdf():
    """上传 PDF → 存附件 → 提取文本 → 返回 JSON。"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有收到文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"})

    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in ('.pdf', '.docx'):
        return jsonify({"success": False, "error": "只支持 PDF 或 Word 文件"})
    try:
        os.makedirs('static/uploads', exist_ok=True)
        safe_name = f"{uuid.uuid4().hex[:10]}{ext}"
        file_path = os.path.join('static', 'uploads', safe_name)
        file.save(file_path)
        try:
            text = extract_resume_text(file_path, file.filename)
        except Exception as ex:
            try: os.remove(file_path)
            except: pass
            return jsonify({"success": False, "error": f"文件解析失败: {str(ex)}"})
        if not text:
            try: os.remove(file_path)
            except: pass
            ocr_hint = " " + ("→ 切换到「📸 图片识别」tab上传截图" if _ocr.available else "→ 当前未安装OCR引擎，建议：①截图后用微信/QQ提取文字 ②安装Tesseract（见上方提示）")
            hint = ("扫描件——文字层为空（可能是图片PDF）" + ocr_hint) if ext == '.pdf' else "请确认文件包含文字内容"
            return jsonify({"success": False, "error": f"文件提取文本为空——{hint}"})

        return jsonify({
            "success": True,
            "text": text,
            "length": len(text),
            "file_path": f"uploads/{safe_name}",
        })
    except Exception as e:
        try: os.remove(file_path)
        except: pass
        return jsonify({"success": False, "error": f"解析失败: {str(e)}"})


@app.route("/api/score", methods=["POST"])
def api_score():
    """JD + 简历文本 → AI 评分 → 返回评分结果 HTML 片段。"""
    jd_text = request.form.get("jd_text", "")
    resume_text = request.form.get("resume_text", "")

    if not resume_text.strip():
        return "<div class='error'>请先上传简历 PDF</div>"

    # 调用 AI 评分
    result = score_resume(jd_text, resume_text)

    if not result["success"]:
        return f"<div class='error'>{result['error']}</div>"

    # 保存到 evaluations 表
    try:
        save_evaluation(
            name=request.form.get("candidate_name", "未知"),
            email=request.form.get("email", ""),
            phone=request.form.get("phone", ""),
            job_title=request.form.get("job_title", "未指定岗位"),
            total=result["total_score"],
            scores_dict=result["scores"],
            jd_text=jd_text,
            resume_text=resume_text,
            token_info=result.get("tokens_used"),
        )
    except Exception as e:
        print(f"[WARN] 保存评估记录失败: {e}")
        result["save_error"] = str(e)

    # 同步写入简历库（resumes 表），让数据分析和简历列表能查到
    try:
        cand_name = request.form.get("candidate_name", "").strip()
        resume_data = {
            "unique_code": f"EVAL-{uuid.uuid4().hex[:8].upper()}",
            "name": cand_name or "未知",
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "resume_text": resume_text,
            "target_position": request.form.get("job_title", "").strip(),
            "interview_status": "筛选",
            "source": "AI评估",
            "tech_direction": "",
            "skills": json.dumps(result.get("highlights", []), ensure_ascii=False),
            "file_path": request.form.get("file_path", "").strip(),
        }
        save_resume(resume_data)
    except Exception as e:
        print(f"[WARN] 同步简历库失败: {e}")

    return render_template("_score_card_v2.html", result=result)


@app.route("/api/followup", methods=["POST"])
def api_followup():
    """评分后追问——SSE 流式返回 AI 回答。"""
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400

    resume_text = data.get("resume_text", "")
    jd_text = data.get("jd_text", "")
    question = data.get("question", "")
    scores_context = data.get("scores", {})
    history = data.get("history", [])  # 前几轮对话: [{"q":"...","a":"..."}, ...]

    if not resume_text.strip():
        return jsonify({"success": False, "error": "缺少简历内容"})

    if not question.strip():
        return jsonify({"success": False, "error": "问题不能为空"})

    def generate():
        """SSE 生成器——把 DeepSeek 流式 token 包装成 SSE 格式。"""
        try:
            for chunk in ask_followup_stream(resume_text, jd_text, scores_context, question, history):
                if chunk is None:
                    break
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # text/event-stream = SSE 协议，浏览器自动处理重连
    return app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # 禁用 nginx 缓冲
        }
    )


@app.route("/api/history")
def api_history():
    """最近评估记录列表（HTML 片段）。"""
    df = get_evaluations(limit=20)
    if df.empty:
        return "<p style='color:#999;text-align:center;padding:20px;'>暂无记录</p>"

    items = ""
    for _, row in df.iterrows():
        items += f"""
        <div class="history-item" onclick="loadHistoryDetail({row['id']})">
            <span class="h-name">{_html.escape(str(row['candidate_name']))}</span>
            <span class="h-job">{_html.escape(str(row['job_title']))}</span>
            <span class="h-score">{row['total_score']}</span>
            <span class="h-time">{(row.get('evaluated_at') or '')[:10]}</span>
        </div>
        """
    return items


# ── 简历库 API ──

@app.route("/api/resumes/list")
def api_resumes_list():
    """简历列表（带筛选），返回 HTML 片段。"""
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "")
    degree = request.args.get("degree", "")
    direction = request.args.get("direction", "")

    df = get_resumes(
        status_filter=status_filter,
        search=search,
        degree=degree,
        direction=direction,
    )

    if df.empty:
        return "<p style='color:#999;text-align:center;padding:40px;'>没有匹配的简历</p>"

    # 动态加载阶段列表，用于状态下拉
    stages = get_stages()
    stage_colors = {}  # name → color 映射
    stage_names = []   # 所有阶段名列表
    for s in stages:
        stage_colors[s["name"]] = s["color"]
        stage_names.append(s["name"])

    cards = ""
    for _, r in df.iterrows():
        status = r.get('interview_status', '') or ''
        file_path = r.get('file_path', '') or ''
        status_color = stage_colors.get(status, '#6e6e73')

        # 状态下拉：当前状态作为默认显示，其他阶段作为切换选项
        other_stages = [n for n in stage_names if n != status]
        stage_opts = "".join(f'<option value="{_html.escape(n)}">{_html.escape(n)}</option>' for n in other_stages)

        skills = ""
        raw_skills = r.get('skills', '')
        if raw_skills:
            try:
                skill_list = json.loads(raw_skills) if isinstance(raw_skills, str) else raw_skills
                skills = " ".join([f"<span class='tag-xs'>{_html.escape(str(s))}</span>" for s in skill_list[:4]])
            except:
                skills = " ".join([f"<span class='tag-xs'>{_html.escape(str(s))}</span>" for s in str(raw_skills).split(',')[:4]])

        school = str(r.get('school', '') or '')
        degree = str(r.get('degree', '') or '')
        company = str(r.get('current_company', '') or '')
        position = str(r.get('current_position', '') or '')
        # 条件显示：空字段不显示该行
        info_rows = ""
        if school or degree:
            info_rows += f'<div class="rc-info-row">{_html.escape(school)}{" · " if school and degree else ""}{_html.escape(degree)}</div>'
        if company or position:
            info_rows += f'<div class="rc-info-row">{_html.escape(company)}{" · " if company and position else ""}{_html.escape(position)}</div>'

        cards += f"""
        <div class='resume-card{" has-file" if file_path else ""}' id='card-{r["id"]}' {"onclick=\"openPdfModal('/'+'"+_html.escape(file_path)+"','"+_html.escape(str(r.get('name','未知')))+"')\"" if file_path else ""}>
            <div class="rc-top">
                <div style="display:flex;align-items:center;gap:var(--space-2);min-width:0;">
                    <span class="rc-name">{_html.escape(str(r.get('name', '未知')))}</span>
                    <span class="rc-status-badge" style="background:{status_color}18;color:{status_color};border:0.5px solid {status_color}40;">{_html.escape(str(status)) if status else '未设置'}</span>
                </div>
                <div class="rc-badges" onclick="event.stopPropagation()">
                    {"<span class='rc-file-badge' title='查看附件简历' onclick=\"event.stopPropagation();openPdfModal('/'+'"+_html.escape(file_path)+"','"+_html.escape(str(r.get('name','未知')))+"')\">📎</span>" if file_path else ""}
                    <select onchange="changeStatus({r['id']}, this.value)" class="status-select">
                        <option value="" selected>{_html.escape(str(status)) if status else '状态'}</option>
                        {stage_opts}
                    </select>
                </div>
            </div>
            <div class="rc-info">{info_rows}</div>
            <div class="rc-skills">{skills}</div>
            <div class="rc-footer">
                <span title="{_html.escape(str(r.get('source', '')))}">{_html.escape(str(r.get('source', '')))} · {(r.get('created_at') or '')[:10]}</span>
                <div class="rc-actions" onclick="event.stopPropagation()">
                    <button onclick="viewEvaluations({r['id']})" class="btn-xs" style="color:var(--accent);">评估</button>
                    <button onclick="deleteCard({r['id']}, event)" class="btn-xs">删</button>
                </div>
            </div>
        </div>
        """

    return cards


@app.route("/resumes/<int:resume_id>/view")
def view_resume_file(resume_id):
    """全屏浏览简历附件 PDF。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT name, file_path FROM resumes WHERE id = ?", (resume_id,)
    ).fetchone()
    conn.close()

    if not row or not row["file_path"]:
        return "<h2>该简历没有附件</h2><a href='/resumes'>返回简历库</a>", 404

    return render_template("pdf_viewer.html",
                           name=row["name"] or "未知",
                           file_url=f"/{row['file_path']}")


@app.route("/api/resumes/status", methods=["POST"])
def api_resume_status():
    """更新面试状态。"""
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400
    try:
        update_status(data["id"], data["status"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/resumes/<int:resume_id>/evaluations")
def api_resume_evaluations(resume_id):
    """查某份简历的历史评估记录。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT email, name FROM resumes WHERE id = ?", (resume_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "简历不存在"})

    email = row["email"] or ""
    name = row["name"] or ""
    df = get_evaluations_for_resume(email, name)

    records = []
    for _, r in df.iterrows():
        scores = {}
        try:
            scores = json.loads(r.get("scores_json", "{}"))
        except:
            pass
        records.append({
            "id": r["id"],
            "job_title": r.get("job_title", ""),
            "total_score": r.get("total_score", 0),
            "scores": scores,
            "evaluated_at": str(r.get("evaluated_at", ""))[:19],
        })

    return jsonify({"success": True, "evaluations": records})


@app.route("/api/resumes/delete", methods=["POST"])
def api_resume_delete():
    """删除简历。"""
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400
    try:
        delete_resume(data["id"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    """内嵌预览 PDF——显式设 Content-Disposition: inline。"""
    file_path = os.path.join('static', 'uploads', filename)
    if not os.path.exists(file_path):
        return "文件不存在", 404
    response = make_response(send_file(file_path, mimetype='application/pdf'))
    response.headers['Content-Disposition'] = 'inline; filename="' + filename + '"'
    return response


@app.route("/api/resumes/import", methods=["POST"])
def api_resumes_import():
    """上传 PDF 直接导入简历库，不走 AI 评估。"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有收到文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"})

    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in ('.pdf', '.docx'):
        return jsonify({"success": False, "error": "只支持 PDF 或 Word 文件"})

    try:
        os.makedirs('static/uploads', exist_ok=True)
        safe_name = f"{uuid.uuid4().hex[:10]}{ext}"
        file_path = os.path.join('static', 'uploads', safe_name)
        file.save(file_path)

        try:
            text = extract_resume_text(file_path, file.filename)
        except Exception as ex:
            return jsonify({"success": False, "error": f"文件解析失败: {str(ex)}"})
        if not text:
            ocr_hint = " " + ("→ 切换到「📸 图片识别」tab上传截图" if _ocr.available else "→ 当前未安装OCR引擎，建议：①截图后用微信/QQ提取文字 ②安装Tesseract（见上方提示）")
            hint = ("扫描件——文字层为空（可能是图片PDF）" + ocr_hint) if ext == '.pdf' else "请确认文件包含文字内容"
            return jsonify({"success": False, "error": f"文件提取文本为空——{hint}"})

        # ── AI 提取简历基本信息 ──
        display_name = "未知"
        email = ""; phone = ""
        school = ""; degree = ""
        company = ""; position = ""
        skills_json = "[]"

        try:
            from ai_scorer import call_deepseek
            extract_prompt = f"""从以下简历文本中提取基本信息，返回纯 JSON（不要 markdown、不要解释）：
{{
  "name": "姓名",
  "email": "邮箱",
  "phone": "手机号",
  "school": "最高学历毕业院校全称",
  "degree": "最高学历（博士/硕士/本科/大专）",
  "company": "最近一段工作的公司全称",
  "position": "最近一段工作的职位",
  "skills": ["技能1", "技能2"]
}}

规则：
- 没找到的字段用空字符串 ""
- skills 取技术关键词，最多8个，中文技能名保留原文（如"机器学习"）
- 只输出 JSON，不要其他文字

简历文本：
{text[:3000]}"""

            ai_content, _ = call_deepseek([
                {"role": "system", "content": "你是简历解析器。只输出JSON，不说废话。"},
                {"role": "user", "content": extract_prompt},
            ], temperature=0.0, max_tokens=500)

            if ai_content:
                clean = ai_content.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                parsed = json.loads(clean)
                display_name = parsed.get("name") or "未知"
                email = parsed.get("email") or ""
                phone = parsed.get("phone") or ""
                school = parsed.get("school") or ""
                degree = parsed.get("degree") or ""
                company = parsed.get("company") or ""
                position = parsed.get("position") or ""
                skills_list = parsed.get("skills") or []
                skills_json = json.dumps([s for s in skills_list if s][:8], ensure_ascii=False)
            else:
                raise Exception("AI 返回空内容")
        except Exception as e:
            print(f"[INFO] AI提取简历信息失败，用文件名兜底: {e}")
            raw_name = os.path.splitext(file.filename)[0].strip()
            if raw_name:
                display_name = raw_name
            # 邮箱电话用正则兜底
            em = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            if em: email = em.group(0)
            pm = re.search(r'1[3-9]\d{9}', text)
            if pm: phone = pm.group(0)

        save_resume({
            "unique_code": f"IMP-{uuid.uuid4().hex[:8].upper()}",
            "name": display_name,
            "email": email,
            "phone": phone,
            "school": school,
            "degree": degree,
            "current_company": company,
            "current_position": position,
            "skills": skills_json,
            "resume_text": text,
            "interview_status": "筛选",
            "source": "手动导入",
            "file_path": f"uploads/{safe_name}",
        })

        return jsonify({"success": True, "name": display_name, "length": len(text)})

    except Exception as e:
        return jsonify({"success": False, "error": f"导入失败: {str(e)}"})


# =============================================================================
# 批量评估 API
# =============================================================================

@app.route("/api/batch/import", methods=["POST"])
def api_batch_import():
    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return jsonify({"success": False, "error": "没有收到文件"})
    if len(files) > 20:
        return jsonify({"success": False, "error": "单次最多20份文件"})
    results = []
    os.makedirs('static/uploads', exist_ok=True)
    for f in files:
        if not f.filename:
            continue
        ext = os.path.splitext(f.filename)[-1].lower()
        if ext not in ('.pdf', '.docx'):
            results.append({"filename": f.filename, "error": "仅支持PDF/Word"})
            continue
        try:
            safe_name = f"{uuid.uuid4().hex[:10]}{ext}"
            file_path = os.path.join('static', 'uploads', safe_name)
            f.save(file_path)
            try:
                text = extract_resume_text(file_path, f.filename)
            except Exception as ex:
                try: os.remove(file_path)
                except: pass
                results.append({"filename": f.filename, "error": f"解析失败:{str(ex)}"})
                continue
            if not text:
                try: os.remove(file_path)
                except: pass
                results.append({"filename": f.filename, "error": "文件提取文本为空"})
                continue
            results.append({
                "filename": f.filename, "text": text, "chars": len(text),
                "file_path": f"uploads/{safe_name}", "success": True,
            })
        except Exception as e:
            results.append({"filename": f.filename, "error": str(e)})
    success_count = sum(1 for r in results if r.get("success"))
    return jsonify({"success": True, "total": len(files), "parsed": success_count, "files": results})


@app.route("/api/batch/quick-filter", methods=["POST"])
def api_batch_quick_filter():
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400
    jd_text = data.get("jd_text", "")
    resumes = data.get("resumes", [])
    if not jd_text.strip():
        return jsonify({"success": False, "error": "请先填写岗位JD"})
    if not resumes:
        return jsonify({"success": False, "error": "没有简历数据"})
    results = quick_match_batch(jd_text, resumes)
    return jsonify({"success": True, "results": results})


@app.route("/api/batch/score", methods=["POST"])
def api_batch_score():
    data = request.get_json()
    if data is None:
        return jsonify({"success": False, "error": "请求格式错误"}), 400
    jd_text = data.get("jd_text", "")
    selected = data.get("selected", [])
    if not selected:
        return jsonify({"success": False, "error": "请至少选择一份简历"})

    def generate():
        import json as _json
        scored = []
        total = len(selected)
        for i, resume in enumerate(selected):
            name = resume.get("name", f"候选人{i+1}")
            text = resume.get("text", "")
            yield f"data: {_json.dumps({'type':'progress','index':i,'total':total,'name':name,'status':'scoring'})}\n\n"
            if not text.strip():
                scored.append({"name":name,"error":"简历文本为空","total_score":0})
                yield f"data: {_json.dumps({'type':'result','index':i,'total':total,'name':name,'error':'简历文本为空'})}\n\n"
                continue
            result = score_resume(jd_text, text)
            entry = {
                "name":name,"success":result["success"],
                "total_score":result.get("total_score",0),
                "scores":result.get("scores",{}),
                "highlights":result.get("highlights",[]),
                "risks":result.get("risks",[]),
                "summary":result.get("summary",""),
                "error":result.get("error"),
            }
            scored.append(entry)
            yield f"data: {_json.dumps({'type':'result','index':i,'total':total,**entry})}\n\n"
        scored.sort(key=lambda x:x["total_score"], reverse=True)
        yield f"data: {_json.dumps({'type':'done','sorted':scored})}\n\n"

    return app.response_class(
        generate(), mimetype='text/event-stream',
        headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'}
    )


@app.route("/api/resumes/export")
def api_resumes_export():
    """导出简历库为 CSV（跟随当前筛选条件）。"""
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "")
    degree = request.args.get("degree", "")
    direction = request.args.get("direction", "")

    df = get_resumes(
        status_filter=status_filter,
        search=search,
        degree=degree,
        direction=direction,
    )
    output = io.StringIO()
    export_df = df.drop(columns=['resume_text', 'scores_json'], errors='ignore')
    export_df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='resumes_export.csv',
    )


# ── AI 数据分析 ──

@app.route("/api/analytics/ai-summary")
def api_analytics_ai_summary():
    """将全部分析数据喂给 DeepSeek，多维度诊断。"""
    from ai_scorer import call_deepseek

    data = get_analytics_data()
    stages = get_stages()

    def build_info(df, col_name):
        """把 DataFrame 的 col_name 列和 count 列拼成文本。"""
        info = ""
        if not df.empty:
            for _, r in df.iterrows():
                info += f"  {r[col_name]}: {r['count']}人\n"
        return info or "  无数据\n"

    funnel_info  = build_info(data["funnel"], "name")
    degree_info  = build_info(data["degree"], "degree")
    direction_info = build_info(data["direction"], "tech_direction")
    source_info  = build_info(data["source"], "source")
    school_info  = build_info(data["school"], "school")
    company_info = build_info(data["company"], "current_company")
    stage_names  = " → ".join(s["name"] for s in stages)

    prompt = f"""你是一位资深招聘总监，手上有完整的人才招聘数据。请从以下所有维度综合分析，给出诊断和建议。

## 管道漏斗（累积计数：每个阶段人数包含了之后所有阶段的人）
  {stage_names}
{funnel_info}

## 学历分布
{degree_info}
## 技术方向分布
{direction_info}
## 渠道来源
{source_info}
## 候选人来源学校 TOP10
{school_info}
## 候选人来源公司 TOP10
{company_info}

## 要求（必须覆盖以下所有维度，缺一不可）

### 1. 管道健康度
- 哪个阶段流失最严重？阶段间转化率多少？
- 可能的原因（2-3条）
- 2-3 条具体改进建议

### 2. 人才画像分析
- 学历结构是否合理？高学历偏多还是偏少？
- 技术方向分布是否符合业务需求？有没有缺的关键方向？
- 1-2 条优化建议

### 3. 渠道效能
- 哪个渠道贡献最多？质量如何（结合转化率推断）？
- 有没有被低估的渠道？
- 1-2 条投放建议

### 4. 人才来源
- 学校/公司来源有什么特征？集中在哪些地方？
- 是否可以拓展新的目标院校/公司？
- 1 条建议

### 5. 整体评价
- 1-2 句话总结当前招聘态势

用简洁 markdown 输出，分小节（##），每条建议前面标序号。直接给结论，不要开场白。"""

    try:
        messages = [
            {"role": "system", "content": "你是资深招聘总监，擅长用数据全面分析招聘全流程。回答覆盖所有数据维度，不遗漏。每条建议具体可执行，不说空话。"},
            {"role": "user", "content": prompt},
        ]
        content, extra = call_deepseek(messages, temperature=0.5, max_tokens=config.ANALYTICS_MAX_TOKENS)
        if content:
            return jsonify({"success": True, "analysis": content})
        return jsonify({"success": False, "error": extra or "AI 调用失败"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── 数据分析 API ──

@app.route("/api/analytics/all")
def api_analytics_all():
    """返回所有图表数据（JSON）。"""
    data = get_analytics_data()
    result = {}
    for key, df in data.items():
        if not df.empty:
            result[key] = df.to_dict(orient='records')
        else:
            result[key] = []

    # 简历总库数 = 全部简历（含未设置状态的）
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
    conn.close()
    result["total_count"] = total

    return jsonify(result)


# =============================================================================
# 启动
# =============================================================================

if __name__ == "__main__":
    # 确保数据库已初始化
    init_db()

    # API Key 已在 config.py 导入时校验，此处不需要额外检查

    # ── 首次启动：自动生成演示数据 ──
    conn_check = get_conn()
    has_data = conn_check.execute("SELECT COUNT(*) FROM resumes").fetchone()[0] > 0
    conn_check.close()
    if not has_data:
        print("[INFO] 简历库为空 → 自动生成演示数据（20份候选人 + 5个岗位）...")
        import generate_mock
        generate_mock.main()
    else:
        print(f"[INFO] 简历库已有 {has_data} 条记录，跳过种子数据生成")

    # 迁移旧数据（如果有）
    legacy_file = "示例简历.json"
    if os.path.exists(legacy_file):
        n = migrate_legacy_data(legacy_file)
        print(f"[OK] 已迁移 {n} 条旧简历数据")
    else:
        print("[INFO] 未找到旧数据文件，跳过迁移")

    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 50)
    print("  简历AI评估系统已启动")
    print(f"  http://localhost:{port}")
    print("=" * 50 + "\n")

    # 线上用 0.0.0.0 + gunicorn，本地用 debug 模式
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="127.0.0.1", port=port)
