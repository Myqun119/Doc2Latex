from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.services.docx_formula_processor import DocxFormulaProcessor
from app.services.omml_converter import OmmlConverter

BASE_DIR = Path(__file__).resolve().parent.parent
IN_DIR = BASE_DIR / "storage" / "in"
OUT_DIR = BASE_DIR / "storage" / "out"

IN_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Doc2LaTeX", version="0.1.0")
processor = DocxFormulaProcessor()
omml_converter = OmmlConverter()


class LatexPreviewRequest(BaseModel):
    latex: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Doc2LaTeX</title>
  <style>
        :root {
            --teal: #36b9cc;
            --teal-dark: #2aa8b8;
            --teal-border: #cff0f8;
            --teal-focus: #86e8de;
            --teal-soft: #f7fefd;
            --mint-border: #a5e9cb;
            --title: #1f2937;
            --body: #4b5563;
            --muted: #9ca3af;
            --success: #52c41a;
            --error: #ff7875;
            --panel-shadow: rgba(54, 185, 204, 0.08);
            --panel-border: rgba(207, 240, 248, 0.95);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            color: var(--body);
            font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
            background:
                radial-gradient(circle at top left, rgba(54, 185, 204, 0.12), transparent 30%),
                radial-gradient(circle at bottom right, rgba(255, 120, 117, 0.08), transparent 28%),
                linear-gradient(135deg, #f8feff 0%, #f4fafc 45%, #fcfeff 100%);
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }

        .wrap {
            max-width: 920px;
            margin: 34px auto;
            padding: 28px;
            border-radius: 12px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.97), rgba(255, 255, 255, 0.92));
            border: 1px solid rgba(255, 255, 255, 0.72);
            box-shadow:
                0 20px 48px rgba(31, 41, 55, 0.06),
                0 10px 30px var(--panel-shadow);
            backdrop-filter: blur(10px);
        }

        .hero {
            position: relative;
            padding: 4px 40px 18px 0;
            border-bottom: 1px solid var(--teal-border);
        }

        .hero::after {
            content: "∑";
            position: absolute;
            top: 2px;
            right: 6px;
            font-size: 30px;
            color: rgba(54, 185, 204, 0.28);
            text-shadow: 0 0 10px rgba(54, 185, 204, 0.08);
        }

        h1 {
            margin: 0;
            color: var(--title);
            font-size: 28px;
            line-height: 1.25;
            font-weight: 700;
            text-shadow: 1px 1px 0 rgba(54, 185, 204, 0.1);
        }

        h2 {
            margin: 0 0 8px 0;
            color: var(--title);
            font-size: 20px;
            line-height: 1.35;
            font-weight: 600;
        }

        p {
            margin: 0;
            color: var(--body);
            font-size: 16px;
            line-height: 1.6;
        }

        .intro { margin-top: 10px; }

        .panel {
            position: relative;
            margin-top: 24px;
            padding: 22px;
            border-radius: 10px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 254, 255, 0.96));
            border: 1px solid var(--panel-border);
            box-shadow:
                0 14px 28px rgba(54, 185, 204, 0.05),
                inset 0 1px 0 rgba(255, 255, 255, 0.86);
            overflow: hidden;
        }

        .panel::before {
            content: "";
            position: absolute;
            inset: 0 auto auto 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, rgba(54, 185, 204, 0.18), rgba(165, 233, 203, 0.36), rgba(54, 185, 204, 0.12));
        }

        .section-divider {
            height: 1px;
            margin: 24px 0 0 0;
            background: var(--teal-border);
        }

        .small {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.6;
        }

        .upload-row {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 14px;
        }

        input[type=file] {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            border: 0;
        }

        .file-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 11px 16px;
            border-radius: 8px;
            border: 1px solid var(--mint-border);
            background: #fff;
            color: var(--title);
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 6px 14px rgba(165, 233, 203, 0.1);
        }

        .file-btn:hover {
            background: #eafbf3;
            border-color: var(--teal);
            transform: translateY(-1px);
        }

        .file-name {
            color: var(--body);
            font-size: 14px;
            min-height: 20px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            border: 0;
            border-radius: 8px;
            padding: 12px 18px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }

        .btn-primary {
            background: var(--teal);
            color: #fff;
            box-shadow:
                0 10px 24px rgba(54, 185, 204, 0.18),
                inset 0 1px 0 rgba(255, 255, 255, 0.18);
        }

        .btn-primary:hover:not(:disabled) {
            background: var(--teal-dark);
            box-shadow:
                0 0 0 2px rgba(207, 240, 248, 0.92),
                0 10px 22px rgba(54, 185, 204, 0.22),
                inset 0 0 0 2px rgba(255, 255, 255, 0.16);
            transform: translateY(-1px);
        }

        .btn:disabled {
            cursor: not-allowed;
            opacity: 0.72;
            transform: none;
            box-shadow: none;
        }

        .example-row {
            margin-top: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }

        .example-toggle {
            background: transparent;
            border: 1px solid transparent;
            color: var(--teal-dark);
            padding: 0;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
        }

        .example-toggle:hover {
            text-decoration: underline;
        }

        .example-box {
            margin-top: 10px;
            padding: 12px 14px;
            border-radius: 8px;
            border: 1px solid #eaf5f7;
            background: linear-gradient(180deg, #fbfeff, #f6fefd);
            display: none;
            color: var(--body);
            line-height: 1.7;
        }

        .example-box.open { display: block; }

        .textarea-wrap { margin-top: 12px; }

        textarea {
            width: 100%;
            min-height: 120px;
            max-height: 320px;
            padding: 14px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #fff;
            color: var(--title);
            font-size: 15px;
            line-height: 1.6;
            font-family: Consolas, "Courier New", monospace;
            resize: vertical;
            outline: none;
            transition: all 0.2s ease;
        }

        textarea:focus {
            border-color: var(--teal-focus);
            box-shadow: 0 0 0 3px rgba(134, 232, 222, 0.2);
        }

        .full-width { width: 100%; }

        .preview {
            min-height: 140px;
            margin-top: 12px;
            padding: 18px;
            border-radius: 8px;
            border: 1px dashed var(--teal-border);
            background: var(--teal-soft);
            text-align: center;
            overflow-x: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }

        .preview:hover { border-color: var(--teal); }

        .preview-placeholder {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.6;
            max-width: 460px;
        }

        .status {
            margin-top: 12px;
            font-size: 14px;
            font-weight: 600;
            min-height: 22px;
        }

        .status.success { color: var(--success); }
        .status.error { color: var(--error); }
        .status.info { color: var(--body); }

        @media (max-width: 860px) {
            .wrap { margin: 18px auto; padding: 18px; border-radius: 10px; }
            h1 { font-size: 24px; }
            .panel { padding: 18px; }
        }
  </style>
    <script>
        function setStatus(message, type) {
            const status = document.getElementById('convertStatus');
            status.className = 'status ' + type;
            status.textContent = message;
        }

        function toggleExample() {
            const panel = document.getElementById('exampleBox');
            panel.classList.toggle('open');
        }

        function updateFileName(input) {
            const fileName = document.getElementById('fileName');
            if (input.files && input.files.length > 0) {
                fileName.textContent = input.files[0].name;
            } else {
                fileName.textContent = '未选择文件';
            }
        }

        function setUploadLoading(button) {
            if (!button) {
                return true;
            }
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = '⏳ 处理中';
            return true;
        }

        async function convertLatexPreview() {
            const latex = document.getElementById('latexInput').value.trim();
            const preview = document.getElementById('formulaPreview');

            if (!latex) {
                setStatus('❌ 请输入 LaTeX 公式', 'error');
                preview.innerHTML = '<div class="preview-placeholder">请输入公式后点击“转换并预览”，这里会显示渲染结果。</div>';
                return;
            }

            setStatus('正在转换并验证...', 'info');

            try {
                const response = await fetch('/latex/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ latex })
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || '转换失败');
                }

                preview.textContent = '$$' + data.normalized_latex + '$$';
                if (window.MathJax && window.MathJax.typesetPromise) {
                    await MathJax.typesetPromise([preview]);
                }

                if (data.word_writable) {
                    setStatus('✅ 验证通过：' + data.message, 'success');
                } else {
                    setStatus('❌ 验证未通过：' + data.message, 'error');
                }
            } catch (error) {
                setStatus('❌ 转换失败：' + error.message, 'error');
            }
        }
    </script>
    <script defer src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js\"></script>
</head>
<body>
    <div class="wrap">
        <div class="hero">
            <h1>Word 公式自动修复与 LaTeX 替换</h1>
            <p class="intro">自动修复Word中的图片公式、文本LaTeX公式，一键转换为可编辑公式</p>
        </div>

        <section class="panel">
            <h2>上传区</h2>
            <p class="small">选择 .docx 文档，一键转换公式，完整保留原文排版</p>
            <form action="/convert" method="post" enctype="multipart/form-data" onsubmit="return setUploadLoading(document.getElementById('uploadButton'))">
                <div class="upload-row">
                    <input id="docFile" type="file" name="file" accept=".docx" required onchange="updateFileName(this)" />
                    <label class="file-btn" for="docFile">选择 .docx 文件</label>
                    <span id="fileName" class="file-name">未选择文件</span>
                </div>
                <div class="upload-row" style="margin-top: 16px;">
                    <button id="uploadButton" class="btn btn-primary" type="submit">上传并转换</button>
                </div>
            </form>
        </section>

        <div class="section-divider"></div>

        <section class="panel" style="margin-top: 24px;">
            <h2>预览验证区</h2>
            <p class="small">输入一段 LaTeX 公式，实时查看渲染效果，验证是否能正确写入Word</p>

            <div class="example-row">
                <button type="button" class="example-toggle" onclick="toggleExample()">展开/收起示例</button>
            </div>
            <div id="exampleBox" class="example-box">
                示例：\\mathbf{x}_{\\mathrm{out}} = \\mathrm{SiLU}(\\mathrm{BN}(\\mathrm{Conv}(\\mathbf{x}_{\\mathrm{in}}))), \\quad (1)
            </div>

            <div class="textarea-wrap">
                <textarea id="latexInput" placeholder="输入 LaTeX 公式，可带或不带 $ 包裹"></textarea>
            </div>

            <div class="upload-row" style="margin-top: 14px;">
                <button type="button" class="btn btn-primary full-width" onclick="convertLatexPreview()">转换并预览</button>
            </div>

            <div id="convertStatus" class="status info"></div>
            <div id="formulaPreview" class="preview" aria-live="polite">
                <div class="preview-placeholder">公式预览区</div>
            </div>
        </section>
  </div>
</body>
</html>
"""


@app.post("/latex/preview")
def latex_preview(payload: LatexPreviewRequest) -> JSONResponse:
    latex = (payload.latex or "").strip()
    if not latex:
        raise HTTPException(status_code=400, detail="latex 不能为空")

    normalized = latex
    if normalized.startswith("$$") and normalized.endswith("$$") and len(normalized) > 4:
        normalized = normalized[2:-2].strip()
    elif normalized.startswith("$") and normalized.endswith("$") and len(normalized) > 2:
        normalized = normalized[1:-1].strip()

    ok, message = omml_converter.validate_latex_for_word(normalized)
    return JSONResponse(
        {
            "word_writable": ok,
            "message": message,
            "normalized_latex": normalized,
        }
    )


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 文件")

    input_name = f"{uuid.uuid4().hex}_{file.filename}"
    output_name = f"converted_{uuid.uuid4().hex}_{file.filename}"
    input_path = IN_DIR / input_name
    output_path = OUT_DIR / output_name

    content = await file.read()
    input_path.write_bytes(content)

    try:
        stats = processor.process(input_path, output_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}") from exc

    if not output_path.exists():
        raise HTTPException(status_code=500, detail="输出文件生成失败")

    return FileResponse(
        path=output_path,
        filename=f"converted_{file.filename}",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "X-Formula-Replaced": str(stats.replaced),
            "X-Image-Formula-Found": str(stats.image_formula_found),
            "X-Text-Latex-Found": str(stats.text_latex_found),
            "X-OMML-Found": str(stats.omml_found),
        },
    )


@app.get("/stats-example")
def stats_example() -> JSONResponse:
    return JSONResponse(
        {
            "replaced": 2,
            "image_formula_found": 2,
            "text_latex_found": 1,
            "omml_found": 4,
        }
    )
