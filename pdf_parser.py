"""
pdf_parser.py — PDF 文本提取
用 PyMuPDF（fitz），C 语言写的解析引擎，Python 只是壳。

核心 API 就三个：
    fitz.open(filepath)   → 打开 PDF，返回 Document 对象
    doc.load_page(n)      → 拿到第 n 页（从 0 开始）
    page.get_text()       → 提取这一页的所有文字

文字 PDF 一行 get_text() 搞定；扫描 PDF（图片）得 OCR，这个文件不涉及。
"""

import os
import fitz  # PyMuPDF 的导入名是 fitz，历史原因


def extract_text(filepath) -> str:
    """从 PDF 文件提取所有文字，返回一个字符串。

    参数:
        filepath: PDF 文件路径（可以是文件对象或字符串路径）

    返回:
        str: 提取到的全部文本。失败返回空字符串。
    """
    text_parts = []  # 存每一页的文字，最后一次性 join
    doc = None       # 防止 finally 里引用未定义的变量

    try:
        # ── 1. 打开 PDF ──
        # fitz.open() 接收文件路径（str）或字节流（BytesIO）
        # 如果是 Flask 上传的文件对象，先读 bytes 再包 BytesIO 传入
        if isinstance(filepath, str):
            doc = fitz.open(filepath)
        else:
            # filepath 是文件对象（bytes），从内存读取
            doc = fitz.open(stream=filepath.read(), filetype="pdf")

        # ── 2. 逐页提取文字 ──
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)       # 拿到第 page_num 页
            page_text = page.get_text()           # 提取这一页的全部文字
            if page_text.strip():                 # 空页跳过（封面、纯图片页）
                text_parts.append(page_text)

    except Exception as e:
        # 损坏的 PDF、加密的 PDF、根本不是 PDF 的文件都会进这里
        print(f"[ERROR] PDF 解析失败: {e}")
        return ""

    finally:
        # ── 3. 无论成功失败，都要关闭文件 ──
        # finally = try 里面不管是否抛异常，这里的代码都会执行
        # 不关的话文件一直被 Python 占着，删不掉移不走
        if doc is not None:
            doc.close()

    return "\n\n".join(text_parts)


def extract_text_docx(filepath) -> str:
    """从 Word (.docx) 文件提取文字（含表格、文本框、页眉页脚）。"""
    from docx import Document
    doc = Document(filepath)
    parts = []
    # 正文段落
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            parts.append(t)
    # 表格
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    # 页眉页脚
    for section in doc.sections:
        for p in section.header.paragraphs:
            t = p.text.strip()
            if t: parts.append(t)
        for p in section.footer.paragraphs:
            t = p.text.strip()
            if t: parts.append(t)

    # 兜底：从底层 XML 提取文字（抓文本框/形状/内容控件里的内容）
    if not parts:
        ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        body = doc.element.body
        for p_elem in body.iter(f'{ns}p'):
            p_text = ''.join(t.text or '' for t in p_elem.iter(f'{ns}t'))
            if p_text.strip():
                parts.append(p_text.strip())

    return "\n\n".join(parts)



# =============================================================================
# 通用提取入口
# =============================================================================

def extract_resume_text(file_obj, filename=""):
    """统一入口：根据文件后缀自动选择 PDF 或 Word 解析。"""
    ext = os.path.splitext(filename)[-1].lower()
    if ext == '.docx':
        return extract_text_docx(file_obj)
    else:
        return extract_text(file_obj)


# =============================================================================
# 启动时自测：解析示例 PDF（如果当前目录有的话）
# =============================================================================
if __name__ == "__main__":
    import os
    import glob

    # 找当前目录下第一个 .pdf 文件
    pdf_files = glob.glob("*.pdf")
    if pdf_files:
        test_file = pdf_files[0]
        print(f"测试解析: {test_file}")
        text = extract_text(test_file)
        print(f"提取字符数: {len(text)}")
        print("-" * 40)
        print(text[:500])  # 只打印前 500 个字符预览
    else:
        print("[INFO] 当前目录没有 PDF 文件，跳过自测")
        print("       把 PDF 拖到这个文件夹，再 python pdf_parser.py")
