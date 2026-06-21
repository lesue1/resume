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
import csv
import json
import html as _html

# 导入自己的模块
import config
from database import (
    init_db, get_conn, get_evaluations, save_evaluation,
    get_resumes, update_status, delete_resume, save_resume,
    get_analytics_data, migrate_legacy_data,
    save_job, get_jobs, get_job, delete_job,
    get_stages, save_stage, delete_stage, reorder_stages,
)
from pdf_parser import extract_text
from ai_scorer import score_resume, ask_followup, ask_followup_stream

# ── OCR 模块（需 Tesseract 系统安装 + Pillow） ──

class OCRService:
    """OCR 识别服务——封装 Tesseract CLI 调用和状态检查。"""

    def __init__(self):
        self.available = False
        self.error = ""
        self._tesseract_exe = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        self._tessdata_dir = ""
        try:
            from PIL import Image
            import os as _os
            self.Image = Image
            if not _os.path.exists(self._tesseract_exe):
                self.error = f"Tesseract 未安装（{self._tesseract_exe} 不存在）"
            else:
                self._tessdata_dir = _os.path.expanduser(r"~/.tesseract/tessdata")
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
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024


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
    """上传 PDF → 提取文本 → 返回 JSON。"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有收到文件"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"})

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"success": False, "error": "只支持 PDF 文件"})

    try:
        text = extract_text(file)  # 传文件对象，pdf_parser 内部处理
        if not text:
            return jsonify({"success": False, "error": "PDF 提取文本为空，可能是扫描件"})

        return jsonify({
            "success": True,
            "text": text,
            "length": len(text),
        })
    except Exception as e:
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

    # 保存到数据库
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
        )
    except Exception as e:
        print(f"[WARN] 保存评估记录失败: {e}")
        result["save_error"] = str(e)

    return render_template("_score_card_v2.html", result=result)


@app.route("/api/followup", methods=["POST"])
def api_followup():
    """评分后追问——SSE 流式返回 AI 回答。"""
    data = request.get_json()
    resume_text = data.get("resume_text", "")
    jd_text = data.get("jd_text", "")
    question = data.get("question", "")
    scores_context = data.get("scores", {})

    if not resume_text.strip():
        return jsonify({"success": False, "error": "缺少简历内容"})

    if not question.strip():
        return jsonify({"success": False, "error": "问题不能为空"})

    def generate():
        """SSE 生成器——把 DeepSeek 流式 token 包装成 SSE 格式。"""
        try:
            for chunk in ask_followup_stream(resume_text, jd_text, scores_context, question):
                if chunk is None:
                    break
                # SSE 格式: data: <内容>\n\n
                # 每个 chunk 是一段文本，用 JSON 包装防止特殊字符干扰
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            # 发送结束信号
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
    stage_opts = ""
    for s in stages:
        stage_opts += f'<option value="{s["name"]}">{s["name"]}</option>'

    cards = ""
    for _, r in df.iterrows():
        status = r.get('interview_status', '') or ''

        skills = ""
        raw_skills = r.get('skills', '')
        if raw_skills:
            try:
                skill_list = json.loads(raw_skills) if isinstance(raw_skills, str) else raw_skills
                skills = " ".join([f"<span class='tag-sm'>{s}</span>" for s in skill_list[:5]])
            except:
                skills = raw_skills

        # 状态标签颜色：从 stages 中匹配
        status_color = "#6e6e73"
        for s in stages:
            if s["name"] == status:
                status_color = s["color"]
                break

        cards += f"""
        <div class="resume-card" id="card-{r['id']}">
            <div class="rc-header">
                <span class="rc-name">{_html.escape(str(r.get('name', '未知')))}</span>
                <span class="rc-status" style="background:{status_color}15;color:{status_color};">{_html.escape(str(status)) if status else '未设置'}</span>
            </div>
            <div class="rc-body">
                <div class="rc-row">{_html.escape(str(r.get('school', '')))} · {_html.escape(str(r.get('degree', '')))} · {_html.escape(str(r.get('major', '')))}</div>
                <div class="rc-row">{_html.escape(str(r.get('current_company', '')))} · {_html.escape(str(r.get('current_position', '')))} · {_html.escape(str(r.get('work_years', '')))}</div>
                <div class="rc-skills">{skills}</div>
            </div>
            <div class="rc-footer">
                <span>{_html.escape(str(r.get('source', '')))} · {(r.get('created_at') or '')[:10]}</span>
                <div class="rc-actions">
                    <select onchange="changeStatus({r['id']}, this.value)" class="status-select">
                        <option value="">状态...</option>
                        {stage_opts}
                    </select>
                    <button onclick="deleteCard({r['id']})" class="btn-sm btn-danger">删</button>
                </div>
            </div>
        </div>
        """

    return cards


@app.route("/api/resumes/status", methods=["POST"])
def api_resume_status():
    """更新面试状态。"""
    data = request.get_json()
    try:
        update_status(data["id"], data["status"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/resumes/delete", methods=["POST"])
def api_resume_delete():
    """删除简历。"""
    data = request.get_json()
    try:
        delete_resume(data["id"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/resumes/export")
def api_resumes_export():
    """导出简历库为 CSV。"""
    df = get_resumes()
    output = io.StringIO()
    # 去掉可能超长的文本列
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
        result = call_deepseek(messages, temperature=0.5)
        if result:
            return jsonify({"success": True, "analysis": result})
        return jsonify({"success": False, "error": "AI 调用失败"})
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
    import os

    # 确保数据库已初始化
    init_db()

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
    app.run(debug=debug, host="0.0.0.0", port=port)
