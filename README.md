# Doc2LaTeX

一个可部署的自动化工具原型，实现以下流程：

1. 用户上传 Word 文档（`.docx`）。
2. 自动识别文档中的图片公式（可扩展到乱码/异常公式规则）。
3. 正则匹配文本 LaTeX 公式（支持 `$$...$$`、`\(...\)`、`\[...\]`、`$...$`）。
3. 将识别结果转换为 LaTeX。
4. 将 LaTeX 重新写回为 Word 可编辑公式对象（优先 OMML，失败时回退文本）。
5. 输出新的 Word 文档并下载。

## 技术栈

- FastAPI：上传/下载接口
- lxml + ZIP：无损读取/回写 DOCX 包结构
- pix2tex（可选）/pytesseract：图片公式识别
- latex2mathml + mathml2omml：LaTeX 到 OMML 转换

## 快速启动

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

浏览器打开：`http://127.0.0.1:8000`

## 接口

- `GET /health`：健康检查
- `GET /`：上传页面
- `POST /convert`：上传 `.docx` 并返回转换后的文档
- `POST /latex/preview`：输入 LaTeX，返回预览内容和是否可写入 Word 原生公式的验证结果

## 关键说明

- 当前支持两类公式链路：图片公式 OCR 转换，以及文本 LaTeX 直接转换。
- 对于 `$$\mathbf{x}_{\mathrm{out}} = \mathrm{SiLU}(\mathrm{BN}(\mathrm{Conv}(\mathbf{x}_{\mathrm{in}}))), \quad (1)$$` 这类块公式，可直接匹配并写回 Word 公式对象。
- 上传页新增了 LaTeX 输入框和“转换并预览”按钮，可实时预览并校验 Word 写入可行性。
- 对“乱码/异常显示公式”的判定，已预留规则扩展点，可根据你的文档样本继续增强。
- 若环境缺少 `mathml2omml` 或转换失败，会回退到文本公式标记（`$...$`），不会破坏文档结构。

## 下一步建议

- 接入更强公式检测模型（区分普通图片和公式截图）。
- 增加对页眉/页脚、批注、文本框中的公式覆盖率。
- 追加转换日志 JSON，标注每个替换位置与置信度。
